# Standard libaries
from math import log, floor
import datetime

# Third party libraries
import pandas as pd
import discord


def human_format(number: float) -> str:
    """
    Takes a number and returns a human readable string.
    Taken from: https://stackoverflow.com/questions/579310/formatting-long-numbers-as-strings-in-python/45846841.

    Parameters
    ----------
    number : float
        The number to be formatted.

    Returns
    -------
    str
        The formatted number as a string.
    """

    # https://idlechampions.fandom.com/wiki/Large_number_abbreviations
    units = ["", "K", "M", "B", "t", "q"]
    k = 1000.0
    try:
        magnitude = int(floor(log(number, k)))
    except ValueError:
        magnitude = 0
        print("Could not get magnitude for number:", number)
    return "%.2f%s" % (number / k**magnitude, units[magnitude])


def format_embed_length(data: list) -> list:
    """
    If the length of the data is greater than 1024 characters, it will be shortened to that amount.

    Parameters
    ----------
    data : list
        The list containing the description for an embed.

    Returns
    -------
    list
        The shortened description.
    """

    for x in range(len(data)):
        if len(data[x]) > 1024:
            data[x] = data[x][:1024].split("\n")[:-1]
            # Fix everything that is not x
            for y in range(len(data)):
                if x != y:
                    data[y] = "\n".join(data[y].split("\n")[: len(data[x])])

            data[x] = "\n".join(data[x])

    return data


# Used in gainers, losers loops
async def format_embed(df: pd.DataFrame, type: str, source: str) -> discord.Embed:
    """
    Formats the dataframe to an embed.

    Parameters
    ----------
    df : pd.DataFrame
        A dataframe with the columns:
        Symbol
        Price
        % Change
        Volume
    type : str
        The type used in the title of the embed
    source : str
        The source used for this data

    Returns
    -------
    discord.Embed
        A Discord embed containing the formatted data
    """

    if source == "binance":
        url = "https://www.binance.com/en/altcoins/gainers-losers"
        color = 0xF0B90B
        icon_url = "https://public.bnbstatic.com/20190405/eb2349c3-b2f8-4a93-a286-8f86a62ea9d8.png"
        name = "Coin"
    elif source == "yahoo":
        url = "https://finance.yahoo.com/" + type
        color = 0x720E9E
        icon_url = (
            "https://s.yimg.com/cv/apiv2/myc/finance/Finance_icon_0919_250x252.png"
        )
        name = "Stock"
    elif source == "coingecko":
        url = "https://www.coingecko.com/en/discover"
        color = 0x8CC63F
        icon_url = "https://static.coingecko.com/s/thumbnail-007177f3eca19695592f0b8b0eabbdae282b54154e1be912285c9034ea6cbaf2.png"
        name = "Coin"
    elif source == "coinmarketcap":
        url = "https://coinmarketcap.com/trending-cryptocurrencies/"
        color = 0x0D3EFD
        icon_url = "https://pbs.twimg.com/profile_images/1504868150403338269/MEQ_lC8P_400x400.jpg"
        name = "Coin"

    e = discord.Embed(
        title=f"Top {len(df)} {type}",
        url=url,
        description="",
        color=color,
        timestamp=datetime.datetime.utcnow(),
    )

    df = df.astype({"Symbol": str, "Price": float, "% Change": float, "Volume": float})

    df = df.round({"Price": 3, "% Change": 2, "Volume": 0})

    # Format the percentage change
    df["% Change"] = df["% Change"].apply(
        lambda x: f" (+{x}% ????)" if x > 0 else f" ({x}% ????)"
    )

    # Post symbol, current price (weightedAvgPrice) + change, volume
    df["Price"] = df["Price"].astype(str) + df["% Change"]

    # Format volume
    df["Volume"] = df["Volume"].apply(lambda x: "$" + human_format(x))

    ticker = "\n".join(df["Symbol"].tolist())
    prices = "\n".join(df["Price"].tolist())
    vol = "\n".join(df["Volume"].astype(str).tolist())

    # Prevent possible overflow
    ticker, prices, vol = format_embed_length([ticker, prices, vol])

    e.add_field(
        name=name,
        value=ticker,
        inline=True,
    )

    e.add_field(
        name="Price",
        value=prices,
        inline=True,
    )

    e.add_field(
        name="Volume",
        value=vol,
        inline=True,
    )

    # Set datetime and icon
    e.set_footer(text="\u200b", icon_url=icon_url)

    return e
