
import validators
import tempfile
import argparse
import requests
import shutil
import json
import phub
import re
import os

#https://phub.readthedocs.io/en/latest/downloading.html
from phub import Quality

from vrp_scrape import VRP_Page
from vrp_scrape import VRP_VideoData
from vrp_scrape import VRP_Authenticate

from collections import namedtuple
VideoFileData = namedtuple('VideoFileData', ['Filename', 'SubFolder', 'File'])

parser = argparse.ArgumentParser(description="Verify and save valid URLs from a file.")
parser.add_argument("-i", "--filename", help="Input file containing 1 URL per line", required=True)
parser.add_argument("-o", "--output-dir", help="Output directory for downloaded videos", required=True)
parser.add_argument("-c", "--config-dir", help="Directory containing config files. VRP requires a ./vrp_cookie_cache and a ./vrp_credentials file", required=True)
GlobalArgs = parser.parse_args()


def detox_filename(filename):
    filename = re.sub(r'[^\w\s-]', '', filename)    
    filename = filename.replace(' ', '_')
    filename = filename.lower()
    
    return filename

def progress(param):
    print(param)
    
def GrabPH(urls, destination_dir):
    grabbed_files = []
    client = phub.Client()
    for url in urls:
        video = client.get(url) 

        subfolder = f"{detox_filename(video.author.name)}-{detox_filename(video.title)}"
        final_name = f"{detox_filename(video.title)}.mp4"
        
        # grab the file into our temp path
        print(f"[PH]Grabbing: {video.title}")
        temp_file = f"{destination_dir}/{final_name}"
        saved_file = video.download(path = temp_file, quality = Quality.BEST)

        grabbed_files.append(VideoFileData(Filename=final_name, SubFolder=subfolder, File=saved_file))
    return grabbed_files


def GrabVRP(urls, destination_dir):

    credentials_filename = f"{GlobalArgs.config_dir}/vrp_credentials"
    cookie_cache_filename = f"{GlobalArgs.config_dir}/vrp_cookie_cache"

    # load in our credentials and authenticate
    auth_credentials = {}
    try:
        with open(credentials_filename, 'r') as json_file:
            auth_credentials = json.load(json_file)
    except FileNotFoundError:
        print(f"[vrp]{credentials_filename} not found.")
        return []

    vrp_auth = VRP_Authenticate(auth_credentials['username'], auth_credentials['password'])
    vrp_auth.LoadCookies(cookie_cache_filename)

    # ensure we are authenticated
    if not vrp_auth.IsAuthenticated():
        vrp_auth.Authenticate()
        if vrp_auth.IsAuthenticated():
            vrp_auth.SaveCookies(cookie_cache_filename)
        else:
            return []
    
    grabbed_files = []
    for url in urls:
        video_page = VRP_Page(url, vrp_auth)
        video_page.obtain()

        target = video_page.find_largest_under_limit("10 GB")
        if target is not None:
            print(f"[VRP]Grabbing: {video_page.Name}({target.Quality})")
            filename = f"{detox_filename(video_page.Name)}-{detox_filename(target.Quality)}.mp4"
            subfolder = f"{detox_filename(video_page.Author)}-{detox_filename(video_page.Name)}-{detox_filename(target.Quality)}"
            target_file = f"{destination_dir}/{filename}"
            target.download_file_with_progress(target_file)

            grabbed_files.append(VideoFileData(Filename=filename, SubFolder=subfolder, File=target_file))
    return grabbed_files

def main():

    if not os.path.exists(GlobalArgs.filename):
        print(f"File '{GlobalArgs.filename}' not found.")
        return
    
    if not os.path.exists(GlobalArgs.output_dir):
        os.makedirs(GlobalArgs.output_dir)
    
    # get all the urls from the file
    with open(GlobalArgs.filename, 'r') as file:
        lines = file.readlines()

        ph_urls = []
        vrp_urls = []
        invalid_urls = []

        for line in lines:
            line = line.strip().lower()
            if validators.url(line):
                if "pornhub" in line:
                    ph_urls.append(line)
                elif "vrporn" in line:
                    vrp_urls.append(line)
                else:
                    invalid_urls.append(line)
            else:
                invalid_urls.append(line)

    # grab every video that is valid
    with tempfile.TemporaryDirectory() as temp_dir:
        obtained_videos = []
        obtained_videos.extend(GrabPH(ph_urls, temp_dir))
        obtained_videos.extend(GrabVRP(vrp_urls, temp_dir))

        for video_data in obtained_videos:
            # ensure our target dir exists
            output_path = f"{GlobalArgs.output_dir}/{video_data.SubFolder}"
            if not os.path.exists(output_path):
                print(f"Creating: {output_path}")
                os.makedirs(output_path)

            # move the file to our target dir
            final_final = f"{output_path}/{video_data.Filename}"
            print(f"Moving to: {final_final}")
            shutil.move(video_data.File, final_final)



if __name__ == "__main__":
    main()