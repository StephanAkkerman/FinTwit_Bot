##> Imports
# > 3rd Party Dependencies
from discord.ext import commands

# Local dependencies
from util.earnings_scraper import YahooEarningsCalendar
from util.confirm_stock import confirm_stock


class Earnings(commands.Cog):
    """
    This class is used to handle the earnings command.
    You can enable / disable this command in the config, under ["COMMANDS"]["EARNINGS"].

    Methods
    -------
    earnings(ctx : commands.context.Context, stock : str) -> None:
        This method is used to handle the earnings command.
    earnings_error(ctx : commands.context.Context, error : Exception) -> None:
        This method is used to handle the errors when using the `!earnings` command.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def earnings(self, ctx: commands.Context, stock: str) -> None:
        """
        Gets next earnings date for a given stock.

        Parameters
        ----------
        ctx : commands.Context
            Necessary Discord context object.
        stock : str
            The stock ticker to get the earnings date for.

        Raises
        ------
        commands.UserInputError
            If the provided stock ticker is not valid.

        Returns
        -------
        None
        """

        if input:
            # Check if this stock exists
            if not await confirm_stock(self.bot, ctx, stock):
                return

            next_earnings = YahooEarningsCalendar().get_next_earnings_date(stock)
            msg = (
                f"The next earnings date for {stock.upper()} is <t:{next_earnings}:R>."
            )
            await ctx.send(msg)
        else:
            raise commands.UserInputError()

    @earnings.error
    async def earnings_error(
        self, ctx: commands.context.Context, error: Exception
    ) -> None:
        print(error)
        if isinstance(error, commands.UserInputError):
            await ctx.send(
                f"{ctx.author.mention} You must specify a stock to request the next earnings of!"
            )
        else:
            await ctx.send(
                f"{ctx.author.mention} An error has occurred. Please try again later."
            )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Earnings(bot))
