
import validators
import subprocess
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

from pytube import YouTube

from functools import partial
from collections import namedtuple
from html import unescape
from xml.etree import ElementTree

VideoFileData = namedtuple('VideoFileData', ['Filename', 'SubFolder', 'File'])

parser = argparse.ArgumentParser(description="Verify and save valid URLs from a file.")
parser.add_argument("-i", "--filename", help="Input file containing 1 URL per line", required=True)
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
        else:
            print(f"Unable to grab video from: {url}")
    return grabbed_files

def GrabYT(urls, destination_dir):
    def on_video_download(stream, chunk, file_handle, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percentage = (bytes_downloaded / total_size) * 100

        file_handle.write(chunk)
        print(f"Downloading \"{stream.title}\" Progress: {percentage:.2f}%")

    def xml_caption_to_srt(self, xml_captions: str) -> str:
        """Convert xml caption tracks to "SubRip Subtitle (srt)".

        :param str xml_captions:
        XML formatted caption tracks.
        """
        segments = []
        root = ElementTree.fromstring(xml_captions)
        i=0
        for child in list(root.iter("body"))[0]:
            if child.tag == 'p':
                caption = ''
                if len(list(child))==0:
                    # instead of 'continue'
                    caption = child.text
                for s in list(child):
                    if s.tag == 's':
                        caption += ' ' + s.text
                caption = unescape(caption.replace("\n", " ").replace("  ", " "),)
                try:
                    duration = float(child.attrib["d"])/1000.0
                except KeyError:
                    duration = 0.0
                start = float(child.attrib["t"])/1000.0
                end = start + duration
                sequence_number = i + 1  # convert from 0-indexed to 1.
                line = "{seq}\n{start} --> {end}\n{text}\n".format(
                    seq=sequence_number,
                    start=self.float_to_srt_time_format(start),
                    end=self.float_to_srt_time_format(end),
                    text=caption,
                )
                segments.append(line)
                i += 1
        return "\n".join(segments).strip()

    grabbed_files = []
    for url in urls:
        
        video = YouTube(url)
        video_stream = video.streams.get_highest_resolution()

        subfolder = f"{detox_filename(video.author)}-{detox_filename(video.title)}"
        final_name = f"{detox_filename(video.title)}.{video_stream.subtype}"
        
        # grab the file into our temp path
        print(f"[PH]Grabbing: {video.title}")
        video_stream.on_progress = partial(on_video_download, video_stream)
        saved_file = video_stream.download(destination_dir, final_name)

        # grab the subtitles if any
        subtitle_tracks = video.captions
        ffmpeg_subtitle_inputs = []
        ffmpeg_subtitle_maps = []
        ffmpeg_subtitle_metadata = []
        index = 0
        for track in subtitle_tracks:
            print(f"Downloading subtitle track: {track.name}")
            
            language_code = track.code
            if language_code.startswith("a."):
                language_code = language_code[2:]

            srt_subtitles = xml_caption_to_srt(track, track.xml_captions)
            srt_subtitles_file_name = f"{final_name}_subtitle_{track.code}.srt"
            
            srt_subtitles_file = os.path.join(destination_dir, srt_subtitles_file_name)
            with open(os.path.join(srt_subtitles_file), 'w', encoding='utf-8') as file:
                file.write(srt_subtitles)

            print(f"Subtitle track '{track.name}' downloaded and converted to {srt_subtitles_file}")

            ffmpeg_subtitle_inputs.append("-i")
            ffmpeg_subtitle_inputs.append(srt_subtitles_file)
            ffmpeg_subtitle_maps.append("-map")
            ffmpeg_subtitle_maps.append(f"{index + 1}") # because map 0 will be the input file later
            ffmpeg_subtitle_metadata.append(f"-metadata:s:s:{index}")
            ffmpeg_subtitle_metadata.append(f"language={language_code}")
            ffmpeg_subtitle_metadata.append(f"-metadata:s:s:{index}")
            ffmpeg_subtitle_metadata.append(f"title={track.name}")

            index += 1


        if index > 0:
            # Combine video and subtitles using ffmpeg
            final_name = f"{detox_filename(video.title)}_with_subtitles.{video_stream.subtype}"
            output_file = os.path.join(destination_dir, final_name)

            ffmpeg_cmd = [
                "ffmpeg",
                "-i", saved_file] + ffmpeg_subtitle_inputs + [
                "-map", "0"] +  ffmpeg_subtitle_maps + [
                "-c:v", "copy",
                "-c:a", "copy",
                "-c:s", "mov_text"] + ffmpeg_subtitle_metadata + [
                 output_file
            ]

            subprocess.run(ffmpeg_cmd)
            grabbed_files.append(VideoFileData(Filename=final_name, SubFolder=subfolder, File=output_file))
        else:
            grabbed_files.append(VideoFileData(Filename=final_name, SubFolder=subfolder, File=saved_file))

    return grabbed_files


def main():

    if not os.path.exists(GlobalArgs.filename):
        print(f"File '{GlobalArgs.filename}' not found.")
        return
    
    # load in output paths
    output_path_config = f"{GlobalArgs.config_dir}/output_paths"
    output_paths = {}
    try:
        with open(output_path_config, 'r') as json_file:
            output_paths = json.load(json_file)
    except FileNotFoundError:
        print(f"[vrp]{output_path_config} not found.")
        return []
    
    # get all the urls from the file
    with open(GlobalArgs.filename, 'r') as file:
        lines = file.readlines()

        ph_urls = []
        yt_urls = []
        vrp_urls = []
        invalid_urls = []

        for line in lines:
            line = line.strip()
            if validators.url(line):
                if "pornhub" in line:
                    ph_urls.append(line)
                elif "vrporn" in line:
                    vrp_urls.append(line)
                elif "youtu" in line: # to get both youtube.com and youtu.be urls
                    yt_urls.append(line)
                else:
                    invalid_urls.append(line)
            else:
                invalid_urls.append(line)

    # use this to move files into a given path
    def move_video(obtained_videos, output_path):
        if output_path == "":
            print(f"Path is empty.  Please configure \"{output_path_config}\"")
            return
        
        # ensure path exists
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        # move if we got some
        for video_data in obtained_videos:
            # ensure our target dir exists
            output_path = f"{output_path}/{video_data.SubFolder}"
            if not os.path.exists(output_path):
                print(f"Creating: {output_path}")
                os.makedirs(output_path)

            # move the file to our target dir
            final_final = f"{output_path}/{video_data.Filename}"
            print(f"Moving to: {final_final}")
            shutil.move(video_data.File, final_final)
            
    # grab every video that is valid
    with tempfile.TemporaryDirectory() as temp_dir:
        move_video(GrabPH(ph_urls, temp_dir), output_paths["pornhub"])
        move_video(GrabVRP(vrp_urls, temp_dir), output_paths["vrporn"])
        move_video(GrabYT(yt_urls, temp_dir), output_paths["youtube"])
        
if __name__ == "__main__":
    main()