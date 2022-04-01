import asyncio

# > 3rd Party Dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop
import pandas as pd

# Local dependencies
from cogs.loops.exchange_data import Binance, KuCoin
from util.ticker import get_stock_info
from util.db import get_db, update_db
from util.disc_util import get_channel, get_user
from util.vars import config, stables, cg_coins, cg
from util.disc_util import get_guild
from util.tv_data import get_tv_data


class Assets(commands.Cog):
    def __init__(self, bot, db=get_db("portfolio")):
        self.bot = bot
        self.trades_channel = get_channel(self.bot, config["TRADES"]["CHANNEL"])

        # Refresh assets
        asyncio.create_task(self.assets(db))

    async def usd_value(self, asset, owned, exchange):

        usd_val = 0

        # Check the corresponding exchange
        if exchange == "binance":
            usd_val = await Binance(self.bot, None, None).get_usd_price(asset)
        elif exchange == "kucoin":
            usd_val = await KuCoin(self.bot, None, None).get_quote_price(
                asset + "-USDT"
            )

        if usd_val == 0:
            if asset in cg_coins["symbol"].values:
                ids = cg_coins[cg_coins["symbol"] == asset]["id"]
                if len(ids) > 1:
                    best_vol = 0
                    coin_dict = None
                    for symbol in ids.values:
                        coin_info = cg.get_coin_by_id(symbol)
                        if "usd" in coin_info["market_data"]["total_volume"]:
                            volume = coin_info["market_data"]["total_volume"]["usd"]
                            if volume > best_vol:
                                best_vol = volume
                                coin_dict = coin_info
                else:
                    coin_dict = cg.get_coin_by_id(ids.values[0])

                try:
                    price = coin_dict["market_data"]["current_price"]["usd"]
                    return price * owned
                except Exception as e:
                    print(e)
                    print("CoinGecko API error for asset:", asset)
                    return 0

            elif tv_data := get_tv_data(asset, "crypto"):
                return tv_data[0] * owned
        else:
            return usd_val * owned

    async def assets(self, db):
        """ 
        Only do this function at startup and if a new portfolio has been added
        Checks the account balances of accounts saved in portfolio db, then updates the assets db
        Posts an overview of everyone's assets in their asset channel
        """

        if db.equals(get_db("portfolio")):
            # Drop all crypto assets
            old_db = get_db("assets")
            crypto_rows = old_db.index[old_db["exchange"] != "stock"].tolist()
            assets_db = old_db.drop(index=crypto_rows)
        else:
            # Add it to the old assets db, since this call is for a specific person
            assets_db = get_db("assets")

        # Ensure that the db knows the right types
        assets_db = assets_db.astype(
            {"asset": str, "owned": float, "exchange": str, "id": "int64", "user": str}
        )

        if not db.empty:

            # Divide per exchange
            binance = db.loc[db["exchange"] == "binance"]
            kucoin = db.loc[db["exchange"] == "kucoin"]

            if not binance.empty:
                for _, row in binance.iterrows():
                    # Add this data to the assets.pkl database
                    assets_db = pd.concat(
                        [assets_db, await Binance(self.bot, row, None).get_data()],
                        ignore_index=True,
                    )

            if not kucoin.empty:
                for _, row in kucoin.iterrows():
                    assets_db = pd.concat(
                        [assets_db, await KuCoin(self.bot, row, None).get_data()],
                        ignore_index=True,
                    )

        # Sum values where assets and names are the same
        assets_db = assets_db.astype(
            {"asset": str, "owned": float, "exchange": str, "id": "int64", "user": str}
        )

        # Get USD value of each asset
        for index, row in assets_db.iterrows():

            # Do not check stocks
            if row["exchange"] == "stock":
                continue

            # Stables is always the same in USD
            if row["asset"] in stables:
                continue

            # Remove small quantities, 0.005 btc is 20 usd
            if round(row["owned"], 3) == 0:
                assets_db.drop(index, inplace=True)
                continue

            usd_val = await self.usd_value(row["asset"], row["owned"], row["exchange"])

            # Remove assets below threshold
            if usd_val < 1:
                assets_db.drop(index, inplace=True)

        # Update the assets db
        update_db(assets_db, "assets")
        print("Updated assets database")

        self.post_assets.start()

    async def format_exchange(self, exchange_df, exchange, e):
        # Sort and clean the data
        sorted_df = exchange_df.sort_values(by=["owned"], ascending=False)

        # Round by 3 and drop everything that is 0
        sorted_df = sorted_df.round({"owned": 3})
        exchange_df = sorted_df.drop(sorted_df[sorted_df.owned == 0].index)

        assets = "\n".join(exchange_df["asset"].to_list())
        owned_floats = exchange_df["owned"].to_list()
        owned = "\n".join(str(x) for x in owned_floats)

        if len(assets) > 1024:
            assets = assets[:1024].split("\n")[:-1]
            owned = "\n".join(owned.split("\n")[: len(assets)])
            assets = "\n".join(assets)
        elif len(owned) > 1024:
            owned = owned[:1024].split("\n")[:-1]
            assets = "\n".join(assets.split("\n")[: len(owned)])
            owned = "\n".join(owned)

        usd_values = []
        for sym in assets.split("\n"):
            if sym not in stables:
                usd_val = 0
                if exchange == "Binance":
                    usd_val = await Binance(self.bot, None, None).get_usd_price(sym)
                elif exchange == "Kucoin":
                    usd_val = await KuCoin(self.bot, None, None).get_quote_price(
                        sym + "-USDT"
                    )
                elif exchange == "Stocks":
                    usd_val = get_stock_info(sym)[3][0]

                if usd_val == 0 and exchange != "Stocks":
                    # Exchange is None, because it is not on this exchange
                    usd_val = await self.usd_value(sym, 1, None)
                usd_values.append(usd_val)
            else:
                usd_values.append(1)

        values = ["$" + str(round(x * y, 2)) for x, y in zip(owned_floats, usd_values)]
        values = "\n".join(values)

        e.add_field(name=exchange, value=assets, inline=True)
        e.add_field(name="Quantity", value=owned, inline=True)
        e.add_field(name="Worth", value=values, inline=True)

        return e

    @loop(hours=12)
    async def post_assets(self):
        assets_db = get_db("assets")
        guild = get_guild(self.bot)

        # Use the user name as channel
        names = assets_db["user"].unique()

        for name in names:
            channel_name = "🌟┃" + name.lower()

            # If this channel does not exist make it
            channel = get_channel(self.bot, channel_name)
            if channel is None:
                channel = await guild.create_text_channel(channel_name)
                print(f"Created channel {channel_name}")

            # Get the data
            assets = assets_db.loc[assets_db["user"] == name]
            id = assets["id"].values[0]
            disc_user = self.bot.get_user(id)

            if disc_user == None:
                disc_user = await get_user(self.bot, id)

            if not assets.empty:
                e = discord.Embed(title="", description="", color=0x1DA1F2,)

                e.set_author(
                    name=disc_user.name + "'s Assets", icon_url=disc_user.avatar_url
                )

                # Divide it per exchange
                binance = assets.loc[assets["exchange"] == "binance"]
                kucoin = assets.loc[assets["exchange"] == "kucoin"]
                stocks = assets.loc[assets["exchange"] == "stock"]

                if not binance.empty:
                    e = await self.format_exchange(binance, "Binance", e)
                if not kucoin.empty:
                    e = await self.format_exchange(kucoin, "KuCoin", e)
                if not stocks.empty:
                    e = await self.format_exchange(stocks, "Stocks", e)

                await channel.send(embed=e)


def setup(bot):
    bot.add_cog(Assets(bot))
