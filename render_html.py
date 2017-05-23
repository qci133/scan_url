import sys
import os
import time
import itertools
from selenium import webdriver
import multiprocessing

DRIVERS = [webdriver.PhantomJS() for _ in range(multiprocessing.cpu_count())]
for one_driver in DRIVERS:
    one_driver.implicitly_wait(10)
    one_driver.set_page_load_timeout(10)


def render(paras):
    html_url, out_path, file_index = paras
    c_process = multiprocessing.current_process()
    process_id = c_process._identity[0] - 1
    driver = DRIVERS[process_id]
    driver.get(html_url)
    driver.save_screenshot(out_path)
    print('worker-{} processed {}'.format(process_id, file_index))


if __name__ == '__main__':
    in_dir = sys.argv[1]
    out_dir = sys.argv[2]

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    all_html_filename = os.listdir(in_dir)
    all_html_path = ['file://' + os.path.abspath(os.path.join(in_dir, _)) for _ in all_html_filename]
    all_output_path = [os.path.join(out_dir, os.path.splitext(_)[0]+'.png') for _ in all_html_filename]

    workers = multiprocessing.Pool(processes=multiprocessing.cpu_count())

    tasks_para = list(zip(all_html_path, all_output_path, itertools.count(1)))

    begin = time.time()
    workers.map_async(render, tasks_para)

    workers.close()
    workers.join()

    for one_driver in DRIVERS:
        one_driver.quit()

    end = time.time()
    print('Total time: {} seconds.'.format(end-begin))
