import asyncio
import aiohttp
from bs4 import BeautifulSoup
from logger import debug_log, info_log
from writer_and_reader import writer
from setting_for_parser import head_browser, url_site


def products_finder(soup_data: BeautifulSoup) -> (list, list):
    """The function of finding the name of the product and its price"""

    products_items = soup_data.find_all('div', class_='product-item')
    names = []
    prices = []
    for data in products_items:
        name = data.find_next(class_='product-item__name').text
        price = data.find_next('span', class_="cur-price").text
        names.append(name)
        prices.append(price)
    return names, prices


def products_cards(names: list, prices: list) -> dict:
    """Function for combining the name and price of the product"""

    assert isinstance(names, list) and isinstance(prices, list), 'Ошибка списков!'
    products = {}
    for name, price in sorted(zip(names, prices), key=lambda x: x[0]):
        if price:
            products[name] = price
        else:
            products[name] = 0
    return products


def link_finder(html_soup: BeautifulSoup) -> (str, str):
    links_nest_catalogs = html_soup.find_all('a', class_="section-item")
    for link_and_name in links_nest_catalogs:
        name_section = link_and_name.text.strip()
        link_section = 'https://www.karat-market.ru' + link_and_name['href']
        yield link_section, name_section


class Parser:
    def __init__(self):
        self.__data_list = list()  # Data sheet to transfer to the writer
        self.__head = head_browser  # information for the site that we are not a bot
        self.__url = url_site  # site link for parsing
        self.__counter = 0  # counter for output to the console

    def __counter_requests(self, name: str) -> None:
        """Function output data to the terminal"""
        self.__counter += 1
        debug_log(f'**** Request {self.__counter}. The data of the "{name}" '
                  f'section has been written to the list of dictionaries! ****')

    async def __tasks_executor(self, session: aiohttp.client.ClientSession, url: str, name_section: str) -> None:
        """Async function to find the right data"""

        async with session.get(url=url, headers=self.__head) as response:
            response_text = await response.text()
            soup = BeautifulSoup(response_text, 'lxml')
            names, prices = products_finder(soup)
            data = products_cards(names, prices)
            if data:
                self.__data_list.append((data, name_section))
                self.__counter_requests(name_section)
                debug_log(f'Query {self.__counter} data added to record sheet')

            else:
                debug_log('Data not found, looping over to find data in subdirectories')

                links_and_names = link_finder(soup)
                for link_section, name_section in links_and_names:
                    await self.__tasks_executor(session, link_section, name_section)

    async def __tasks_manager(self) -> None:
        """Async function to set the request processing queue"""
        async with aiohttp.ClientSession() as session:
            info_log('Sending a request to the server')

            response = await session.get(url=self.__url, headers=self.__head)
            info_log(f'Server response received {response.status}')

            soup = BeautifulSoup(await response.text(), 'lxml')
            links_and_names = link_finder(soup)
            tasks = []
            for link_section, name_section in links_and_names:
                task = asyncio.create_task(self.__tasks_executor(session, link_section, name_section))
                tasks.append(task)
                debug_log('Task manager created successfully!')
            await asyncio.gather(*tasks)

            info_log('All data collected!')
            info_log('Data transferred for writing!')

            # print('##### All data collected! #####\n'
            #       '##### Data transferred for writing! #####')
            writer(self.__data_list)

    def start_collecting(self) -> None:
        asyncio.run(self.__tasks_manager())
