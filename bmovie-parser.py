import re
from bs4 import BeautifulSoup
import pandas as pd

with open('bmovie.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

items = soup.select("li.ipc-metadata-list-summary-item")

imdb_ids = []

for item in items:
    link_tag = item.find("a", href=re.compile(r"^/title/tt\d+"))
    if link_tag:
        href = link_tag["href"]
        match = re.search(r"/title/tt(\d+)", href)
        if match:
            imdb_id = match.group(1)  # Just the numeric part
            imdb_ids.append(imdb_id)


bmovies_df = pd.DataFrame(imdb_ids, columns=["ID"])
bmovies_df.to_csv('bmovies.csv', index=False)
