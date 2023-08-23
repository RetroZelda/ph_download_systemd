
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

            subfolder = f"{detox_filename(video.author.name)}-{detox_filename(video.title)}"
            final_name = f"{detox_filename(video.title)}.mp4"
            
            # grab the file into our temp path
            print(f"Grabbing: {video.title}")
            temp_file = f"{temp_dir}/{final_name}"
            saved_file = video.download(path = temp_file, quality = Quality.BEST)

            # ensure our target dir exists
            output_path = f"{args.output_dir}/{subfolder}"
            if not os.path.exists(output_path):
                print(f"Creating: {output_path}")
                os.makedirs(output_path)

            # move the file to our target dir
            final_final = f"{output_path}/{final_name}"
            print(f"Moving to: {final_final}")
            shutil.move(saved_file, final_final)



if __name__ == "__main__":
    main()