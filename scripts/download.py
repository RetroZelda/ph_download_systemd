
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

from pytubefix import YouTube
from pytubefix import Playlist
from pytubefix import exceptions

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

        subfolder = f"{detox_filename(video.author.name)}"
        final_name = f"{detox_filename(video.title)}.mp4"
        
        # grab the file into our temp path
        print(f"[PH] Grabbing: {video.title}")
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
        print(f"[vrp] {credentials_filename} not found.")
        return []

    vrp_auth = VRP_Authenticate(auth_credentials['username'], auth_credentials['password'])
    vrp_auth.LoadCookies(cookie_cache_filename)

    # ensure we are authenticated
    if not vrp_auth.IsAuthenticated():
        if vrp_auth.Authenticate():
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
            subfolder = f"{detox_filename(video_page.Author)}"
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
        print(f"[Youtube] Downloading Video \"{stream.title}\" Progress: {percentage:.2f}%")

    def on_audio_download(stream, chunk, file_handle, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percentage = (bytes_downloaded / total_size) * 100

        file_handle.write(chunk)
        print(f"[Youtube] Downloading Audio \"{stream.title}\" Progress: {percentage:.2f}%")

    def xml_caption_to_srt(self, xml_captions: str) -> str:
        """Convert xml caption tracks to "SubRip Subtitle (srt)".

        :param str xml_captions:
        XML formatted caption tracks.
        """
        segments = []
        root = ElementTree.fromstring(xml_captions)
        i=0
        for child in root:
            if child.tag == 'text':
                caption = ''
                if len(list(child))==0:
                    # instead of 'continue'
                    caption = child.text
                    if caption is None:
                        caption = ""
                for s in list(child):
                    if s.tag == 's':
                        caption += ' ' + s.text
                caption = unescape(caption.replace("\n", " ").replace("  ", " "),)
                try:
                    duration = float(child.attrib["dur"])
                except KeyError:
                    duration = 0.0
                start = float(child.attrib["start"])
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
        
        videos = []
        playlist_path = None
        use_oauth = False
        oauth_cache = False
        if "list" in url:
            playlist = Playlist(url)
            print(f"[Youtube] Found Playlist: {playlist.title}")
            playlist_path = f"{detox_filename(playlist.owner)}/{detox_filename(playlist.title)}"
            for playlist_video in playlist.video_urls:
                videos.append(YouTube(playlist_video + "&has_verified=1", use_oauth=use_oauth, allow_oauth_cache=oauth_cache))
        else:
            videos.append(YouTube(url + "&has_verified=1", use_oauth=use_oauth, allow_oauth_cache=oauth_cache))

        for video in videos:
            video_stream = None
            try:
                if video.age_restricted:
                    video.bypass_age_gate()
                video_stream = None
                audio_stream = None
                for stream in video.streams.filter(file_extension='mp4', type='video').order_by('resolution').desc():
                    if stream.includes_video_track:
                        video_stream = stream
                        break
                
                if video_stream and not video_stream.includes_audio_track:
                    for stream in video.streams.filter(file_extension='mp4', type='audio').order_by('bitrate').desc():
                        if stream.includes_audio_track:
                            audio_stream = stream
                            break

            except exceptions.AgeRestrictedError:
                print(f'Video {video.title} is age restricted, skipping.')
                continue
            except exceptions.MembersOnly:
                print(f'Video {video.title} is for members only, skipping.')
                continue
            except exceptions.VideoPrivate:
                print(f'Video {video.title} is private, skipping.')
                continue
            except exceptions.VideoRegionBlocked:
                print(f'Video {video.title} is region blocked, skipping.')
                continue
            except exceptions.LiveStreamError:
                print(f'Video {video.title} is a live stream, skipping.')
                continue
            except exceptions.VideoUnavailable:
                print(f'Video {video.title} is unavaialable, skipping.')
                continue

            if video_stream is None:
                print(f'Video {video.title} doesnt have a valid video stream, skipping.')
                continue

            if not video_stream.includes_audio_track and audio_stream is None:
                print(f'Video {video.title} doesnt have a valid audio stream. Continuing without audio.')
                

            subfolder = playlist_path if playlist_path is not None else f"{detox_filename(video.author)}"
            final_name = f"{detox_filename(video.title)}.{video_stream.subtype}"
            
            # grab the files into our temp path
            print(f"[Youtube] Grabbing Video: {video.title}")
            video_stream.on_progress = partial(on_video_download, video_stream)

            saved_video = None
            try:
                saved_video = video_stream.download(destination_dir, "temp_v_" + final_name)
            except:
                print(f'Video {video.title} is unable to download, skipping.')
                continue

            saved_audio = None
            if audio_stream is not None:
                print(f"[Youtube] Grabbing Audio: {video.title}")
                audio_stream.on_progress = partial(on_audio_download, audio_stream)
                try:
                    saved_audio = audio_stream.download(destination_dir, "temp_a_" + f"{detox_filename(video.title)}.{audio_stream.subtype}")
                except:
                    print(f'Audio for {video.title} was unable to download.')
                    saved_audio = None

            if saved_audio is not None:
                combined_file = "temp_c_" + f"{detox_filename(video.title)}.{video_stream.subtype}"
                ffmpeg_command = [
                    'ffmpeg',
                    '-y',
                    '-i', saved_video,        # Input video file
                    '-i', saved_audio,        # Input audio file
                    '-c', 'copy',            # Copy codec (no re-encoding)
                    '-map', '0:v',           # Map video stream from first input
                    '-map', '1:a',           # Map audio stream from second input
                    combined_file
                ]

                # Execute the ffmpeg command
                print(f"[Youtube] Joining Video and Audio: {video.title}")
                subprocess.run(ffmpeg_command)
                os.remove(saved_video)
                os.remove(saved_audio)
                saved_video = combined_file
                

            # grab the subtitles if any
            subtitle_tracks = video.captions
            ffmpeg_subtitle_inputs = []
            ffmpeg_subtitle_maps = []
            ffmpeg_subtitle_metadata = []
            index = 0
            for track in subtitle_tracks:
                print(f"[Youtube] Downloading subtitle track: {track.name}")
                
                language_code = track.code
                if language_code.startswith("a."):
                    language_code = language_code[2:]

                srt_subtitles = xml_caption_to_srt(track, track.xml_captions)
                srt_subtitles_file_name = f"{final_name}_subtitle_{track.code}.srt"
                
                srt_subtitles_file = os.path.join(destination_dir, srt_subtitles_file_name)
                with open(os.path.join(srt_subtitles_file), 'w', encoding='utf-8') as file:
                    file.write(srt_subtitles)

                print(f"[Youtube] Subtitle track '{track.name}' downloaded and converted to {srt_subtitles_file}")

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
                output_file = os.path.join(destination_dir, final_name)

                ffmpeg_cmd = [
                    "ffmpeg",
                    '-y',
                    "-i", saved_video] + ffmpeg_subtitle_inputs + [
                    "-map", "0"] +  ffmpeg_subtitle_maps + [
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-c:s", "mov_text"] + ffmpeg_subtitle_metadata + [
                    output_file
                ]

                print(f"[Youtube] Baking the subtitles")
                subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                os.remove(saved_video)
                grabbed_files.append(VideoFileData(Filename=final_name, SubFolder=subfolder, File=output_file))
            else:
                grabbed_files.append(VideoFileData(Filename=final_name, SubFolder=subfolder, File=saved_video))

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
            final_path = f"{output_path}/{video_data.SubFolder}"
            if not os.path.exists(final_path):
                print(f"Creating: {final_path}")
                os.makedirs(final_path)

            # move the file to our target dir
            final_final = f"{final_path}/{video_data.Filename}"
            print(f"Moving to: {final_final}")
            shutil.move(video_data.File, final_final)
            
    # grab every video that is valid
    with tempfile.TemporaryDirectory() as temp_dir:
        move_video(GrabPH(ph_urls, temp_dir), output_paths["pornhub"])
        move_video(GrabVRP(vrp_urls, temp_dir), output_paths["vrporn"])
        move_video(GrabYT(yt_urls, temp_dir), output_paths["youtube"])
        
if __name__ == "__main__":
    main()