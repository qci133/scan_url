import sys
import os
import time
import itertools
from selenium import webdriver
import multiprocessing


DRIVER = None


def render(paras):
    global DRIVER
    html_url, out_path, file_index = paras
    if DRIVER is None:
        DRIVER = webdriver.PhantomJS()
        DRIVER.implicitly_wait(10)
        DRIVER.set_page_load_timeout(10)
        DRIVER.viewportSize = {'width': 1280, 'height': 800}
        DRIVER.maximize_window()
    try:
        DRIVER.get(html_url)
        DRIVER.save_screenshot(out_path)
        c_process = multiprocessing.current_process()
        print('worker-{} processed {}'.format(c_process._identity[0] - 1, file_index))
    except:
        DRIVER.close()
        DRIVER = None


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

    for one_driver in DRIVER:
        one_driver.quit()

    end = time.time()
    print('Total time: {} seconds.'.format(end-begin))
