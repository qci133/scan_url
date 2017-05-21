#!/usr/bin/env python3.5
# coding: utf-8

import asyncio
import aiohttp
import urllib
import time
import sys
import os
import traceback
import logging


LOGGER = logging.getLogger(__name__)


class Scanner:
    """Scan URLs to detect if they exists."""

    def __init__(self, task_queue, max_tries, timeout, results, loop):
        self.queue = task_queue
        self.max_tries = max_tries
        self.timeout = timeout
        self.results = results
        self.loop = loop
        # FIXME: check if one session can used to get different websites
        # FIXME: check if read_timeout and conn_timeout is valid
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, sdch",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "close",
            "Cookie": "_gauges_unique_hour=1; _gauges_unique_day=1; _gauges_unique_month=1; _gauges_unique_year=1; _gauges_unique=1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
            }

    def close(self):
        """Close resources."""
        self.session.close()

    async def work(self):
        """Process every url in queue forever."""
        try:
            while True:
                url = await self.queue.get()
                LOGGER.warning('get a url %r', url)
                await self.detect(url)
                LOGGER.warning('begin task_done url %r', url)
                self.queue.task_done()
                LOGGER.warning('finished task_done url %r', url)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            LOGGER.warning('exception %r', e)     # NOTE: if exception happens here, the queue will not task_done

    async def detect(self, url):
        """Fetch one URL."""
        tries = 0
        # example: "Host": "httpbin.org", "Referer": "http://httpbin.org/",
        scheme, host, path, params, query, fragment = urllib.parse.urlparse(url)
        referer = '://'.join([scheme, host])
        self.headers['Host'] = host
        self.headers['Referer'] = referer
        while tries < self.max_tries:
            try:
                LOGGER.warning('begin get url %r', url)
                response = await self.session.get(url, headers=self.headers, timeout=self.timeout,
                                                  allow_redirects=True)
                LOGGER.warning('end get url %r', url)

                if tries > 0:
                    LOGGER.info('try %r for %r success', tries+1, url)

                break
            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                LOGGER.warning('try %r for %r raised %r', tries+1, url, error)
            except Exception as error:
                traceback.print_exc()
                LOGGER.error('try %r for %r raised %r', tries+1, url, error)

            tries += 1
        else:
            # We never broke out of the loop: all tries failed.
            LOGGER.warning('%r failed after %r tries', url, self.max_tries)
            return

        has_exception = False
        try:
            if response.status != 404:
                LOGGER.warning('begin read url %r', url)
                resp_body = await response.read()
                LOGGER.warning('end read url %r', url)
                self.results.append((url, resp_body))
                LOGGER.info('Success detecting url %r', url)
        except Exception as e:
            has_exception = True
            LOGGER.warning('Failed detecting url %r, %r', url, e)
        finally:
            if has_exception:
                LOGGER.warning('begin release the %r', url)
            await response.release()    # FIXME: check how response is released
            if has_exception:
                LOGGER.warning('end release the %r', url)
            return


def load_urls(f_path):
    with open(f_path, 'rt') as h:
        lines = [urllib.parse.unquote(_.strip()) for _ in h]
    urls = filter(is_candidate_url, lines)
    return urls


def is_candidate_url(url):
    """Judge if the url has some parameters or long path."""
    if url is None or url == '':
        return False
    scheme, netloc, path, params, query, fragment = urllib.parse.urlparse(url)
    if scheme not in ('http', 'https'):
        return False
    if path == '' and params == '' and query == '' and fragment == '':
        return False
    return True


def show_usage(program):
    print('Usage: python3.5 {} urls_file out_file detail_dir retry_times'
          ' time_out(float) max_tasks [-(v)erbose]'.format(program))


async def scan(urls, max_tasks, loop, store_result):
    begin = time.time()
    try:
        queue = asyncio.Queue(loop=loop)
        for one_url in urls:
            queue.put_nowait(one_url)

        scanners = [Scanner(queue, retry, time_out, store_result, event_loop) for _ in range(max_tasks)]
        tasks = [asyncio.ensure_future(_.work(), loop=loop) for _ in scanners]

        await queue.join()  # block until all urls in queue has been consumed completely
    except Exception as e:
        LOGGER.warning('scan recv exception %r', e)
    finally:
        for index, task in enumerate(tasks):
            LOGGER.warning('begin cancel task %r', index)
            task.cancel()
            LOGGER.warning('end cancel task %r', index)
        for scanner in scanners:
            scanner.close()

        sys.stdout.flush()
        sys.stderr.flush()
        end = time.time()
        print('Time used: {} seconds.'.format(end-begin))

if __name__ == '__main__':
    if len(sys.argv) != 7 and len(sys.argv) != 8:
        show_usage(sys.argv[0])
        sys.exit(0)
    urls_file = sys.argv[1]
    out_file = sys.argv[2]
    detail_dir = sys.argv[3]
    retry = int(sys.argv[4])
    time_out = float(sys.argv[5])
    concurrent = int(sys.argv[6])

    if not os.path.exists(detail_dir):
        os.makedirs(detail_dir)

    event_loop = asyncio.get_event_loop()

    verbose = False
    if len(sys.argv) == 8:
        verbose = (sys.argv[7] == '-v' or sys.argv[7] == '-verbose')

    if verbose:
        event_loop.set_debug(True)
        logging.getLogger('asyncio').setLevel(logging.DEBUG)

    logging.basicConfig(level=logging.INFO if verbose else logging.ERROR,
                        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S')

    all_urls = load_urls(urls_file)

    results = list()
    try:
        event_loop.run_until_complete(scan(all_urls, concurrent, event_loop, results))
    except Exception as e:
        LOGGER.warning('%r', e)

    with open(out_file, 'wt') as ho:
        for index, item in enumerate(sorted(results)):
            url, body = item
            ho.write('{} {}'.format(index, url))
            ho.write('\n')
            with open(os.path.join(detail_dir, str(index)+'.html'), 'wb') as w_detail:
                w_detail.write(body)

    # next two lines are required for actual aiohttp resource cleanup
    event_loop.stop()
    event_loop.run_forever()

    event_loop.close()
