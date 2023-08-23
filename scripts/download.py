
import validators
import tempfile
import argparse
import shutil
import phub
import re
import os

#https://phub.readthedocs.io/en/latest/downloading.html

from phub import Quality

def detox_filename(filename):
    filename = re.sub(r'[^\w\s-]', '', filename)    
    filename = filename.replace(' ', '_')
    filename = filename.lower()
    
    return filename

def progress(param):
    print(param)

def main():

    parser = argparse.ArgumentParser(description="Verify and save valid URLs from a file.")
    parser.add_argument("-i", "--filename", help="Input file containing 1 URL per line", required=True)
    parser.add_argument("-o", "--output-dir", help="Output directory for downloaded videos", required=True)
    args = parser.parse_args()

    if not os.path.exists(args.filename):
        print(f"File '{args.filename}' not found.")
        return
    
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # get all the urls from the file
    with open(args.filename, 'r') as file:
        lines = file.readlines()

        valid_urls = []
        invalid_urls = []

        for line in lines:
            line = line.strip()
            if validators.url(line):
                valid_urls.append(line)
            else:
                invalid_urls.append(line)

    # grab every video that is valid
    with tempfile.TemporaryDirectory() as temp_dir:
        client = phub.Client()
        for url in valid_urls:
            video = client.get(url) 

            temp_path = f"{temp_dir}/{detox_filename(video.author.name)}-{detox_filename(video.title)}.mp4"
            final_path = f"{args.output_dir}/{detox_filename(video.author.name)}-{detox_filename(video.title)}.mp4"

            print(f"Grabbing: {video.title}")
            saved_file = video.download(path = temp_path, quality = Quality.BEST)

            print(f"Moving to: {final_path}")
            shutil.move(saved_file, final_path)



if __name__ == "__main__":
    main()