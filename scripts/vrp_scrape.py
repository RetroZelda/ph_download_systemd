import json
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup

class VRP_Authenticate:
    def __init__(self, username, password):
        self.Username = username
        self.Password = password
        self.BaseURL = "https://vrporn.com"
        self.LoginURL = f"{self.BaseURL}/login"
        self.Cookies = {}

    def SaveCookies(self, filename):
        with open(filename, 'w') as json_file:
            json.dump(self.Cookies, json_file)
    
    def LoadCookies(self, filename):
        try:
            with open(filename, 'r') as json_file:
                self.Cookies = json.load(json_file)
            #print(f"Loaded Cookies: {self.Cookies}")
        except FileNotFoundError:
            print(f"{filename} not found")
        except json.decoder.JSONDecodeError:
            print(f"{filename} has invalid JSON")

    def IsAuthenticated(self):
        url = f"{self.BaseURL}/account"

        # Fetch the webpage
        response = requests.get(url, cookies=self.Cookies)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the span element with class "account-name"
            account_name_span = soup.find('span', class_='account-name')

            if account_name_span:
                # Print the text content of the found span
                print("Authenticated as:", account_name_span.text)
                return True
        print(f"Not Authenticated")
        return False
    
    def Authenticate(self):
        # Fetch the login page
        response = requests.get(self.LoginURL)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract form details
            login = soup.find('div', {'class': 'um-form'})
            form = login.find('form', {'id': 'login-form'})
            action_url = f"{self.BaseURL}{form.get('action')}"
            
            # Prepare login data
            data = {
                'username': self.Username,
                'user_password': self.Password,
            }

            # Make a POST request to login
            response = requests.post(action_url, data=data)

            if response.status_code == 200:
                print("Login successful!")

                # Print the cookies received in the response
                print("Cookies:", response.cookies.get_dict())
                self.Cookies = response.cookies.get_dict()
                return True
            else:
                print(f"Login failed. Status code: {response.status_code}")
        else:
            print(f"Failed to fetch login page. Status code: {response.status_code}")
        return False

class VRP_VideoData:
    def __init__(self, quality, size, link):
        self.Quality = quality
        self.Size = size
        self.Link = link

    def download_file(self, destination):
        response = requests.get(self.Link, stream=True)
        if response.status_code == 200:
            with open(destination, 'wb') as file:
                for chunk in response.iter_content(chunk_size=128):
                    file.write(chunk)
            print(f"File downloaded successfully to {destination}")
        else:
            print(f"Failed to download the file. Status code: {response.status_code}")

    def download_file_with_progress(self, destination):
        response = requests.get(self.Link, stream=True)
        total_size = int(response.headers.get('content-length', 0))

        with open(destination, 'wb') as file, tqdm(
            desc=destination,
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in response.iter_content(chunk_size=1024):
                file.write(chunk)
                bar.update(len(chunk))

        print(f"File downloaded successfully to {destination}")

class VRP_Page:
    def __init__(self, url, auth):
        self.URL = url
        self.Auth = auth
        self.Links = []

    def obtain(self):
        # Send an HTTP request to the webpage with the provided cookies
        response = requests.get(self.URL, cookies=self.Auth.Cookies)
        
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the HTML content of the page
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # get the video name
            self.Name = soup.find('h1', class_='content-title').text.strip()

            # get the video's studio
            self.Author = soup.find('a', id='studio-logo').text.strip()

            # Find the div element with class "download-links-popup"
            download_div = soup.find('div', class_='download-links-popup')
            
            # Check if the div element was found
            if download_div:

                # Find the hidden "list_row" that holds all the download links
                links_div = soup.find('div', class_='list_row')
                list_rows = links_div.find_all('div', {'class': 'download-btn vr-download paid-download'})
                
                # if its 0 then we are probably a free account
                if len(list_rows) is 0:
                    list_rows = links_div.find_all('div', {'class': 'download-btn vr-download free-download'})
                    
                # scrape each link
                for row in list_rows:

                    # check for a "premium only" text
                    premium_elemt = row.find('span', class_='text_login')
                    if premium_elemt is not None:
                        print("Found premium only link")
                        continue

                    # build our info
                    link = row.attrs['data']
                    quality = row.attrs['id']
                    size = "0"

                    # get the text for hte name and the filesize
                    size = row.find('span', class_='right').text
                    quality_element = row.find('span', class_='text_long')
                    if quality_element is not None:
                        quality = quality_element.text.replace("Max Quality ", "")

                    self.Links.append(VRP_VideoData(quality=quality, size=size, link=link))
            else:
                print("Div element with class 'download-links-popup' not found.")
        else:
            print(f"Failed to retrieve the webpage. Status code: {response.status_code}")

    def find_largest_under_limit(self, limit):
        # Function to convert file size text to bytes
        def convert_to_bytes(target_link):
            units = {'KB': 1e3, 'MB': 1e6, 'GB': 1e9, 'TB': 1e12}
            size, unit = target_link.split()
            return float(size) * units[unit]

        # Convert the limit to bytes
        limit_bytes = convert_to_bytes(limit)

        # Filter file sizes that are under or equal to the limit
        valid_sizes = [link for link in self.Links if convert_to_bytes(link.Size) <= limit_bytes]

        # If there are valid sizes, return the largest one; otherwise, return None
        return max(valid_sizes, key=lambda x: convert_to_bytes(x.Size), default=None)
