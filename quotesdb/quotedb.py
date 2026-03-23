import datetime
import random

import discord
from redbot.core import Config, commands


IDENTIFIER = 1672261474290237490

default_guild = {
    "cooldown": 30,
    "banlist": [],
    "spam_channels": [],
    "quotes": {
        "incr": 1,
        "id": {},
        "trigger": {}
    }
}


class QuoteDB(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=IDENTIFIER, force_registration=True
        )

        self.config.register_guild(**default_guild)
        self.cooldowns = {}


    @commands.guild_only()
    @commands.command(name=".")
    async def quote_add(self, ctx, trigger: str, *, quote: str):
        'Add a new quote'

        guild_group = self.config.guild(ctx.guild)

        async with guild_group.banlist() as banlist:
            if ctx.author.id in banlist:
                await ctx.send(f"{ctx.author.mention}, you are banned from adding quotes.")
                return

        incr = await guild_group.quotes.incr() + 1
        await guild_group.quotes.incr.set(incr)

        async with guild_group.quotes.id() as quotes, guild_group.quotes.trigger() as triggers:
            quotes[incr] = {
                "content": quote,
                "user": ctx.author.id,
                "trigger": trigger,
                "jump_url": ctx.message.jump_url,
                "datetime": datetime.datetime.now().timestamp()
            }

            triggers.setdefault(trigger, [])
            triggers[trigger] += [str(incr)]

        await ctx.send(f"{ctx.author.mention} added quote `#{incr}`.")


    @commands.guild_only()
    @commands.command(name="setcd")
    async def set_cooldown(self, ctx, new_cooldown):
        'Set the command invoke cooldown'

        if not ctx.author.guild_permissions.manage_channels:
            await ctx.send(f"{ctx.author.mention}, only users with manage_channels permissions can use this command.")
            return

        if not new_cooldown.isdigit():
            await ctx.send("New cooldown must be an integer.")
            return

        new_cooldown = int(new_cooldown)

        if new_cooldown < 5 or new_cooldown > 300:
            await ctx.send("New cooldown must be between 5 to 300 seconds (5 minutes).")
            return

        guild_group = self.config.guild(ctx.guild)
        await guild_group.cooldown.set(new_cooldown)

        await ctx.send(f"{ctx.author.mention} successfully set the cooldown to {new_cooldown} seconds.")


    # custom cooldown function just because the built in
    # options do not work in this exact case scenario
    async def check_cooldown(self, ctx):
        id_str = f"{ctx.author.id}"
        current_time = datetime.datetime.now().timestamp()
        del_ids = []

        guild_group = self.config.guild(ctx.guild)
        cooldown_s = await guild_group.cooldown()

        for cd in self.cooldowns:
            if current_time - self.cooldowns[cd] > cooldown_s:
                del_ids.append(cd)

        for del_id in del_ids:
            del self.cooldowns[del_id]

        if id_str not in self.cooldowns:
            self.cooldowns[id_str] = current_time
            return False

        await ctx.send(f"{ctx.author.mention}, you are on cooldown, time remaining: {((self.cooldowns[id_str] + cooldown_s) - current_time):.1f}.")
        return True


    @commands.guild_only()
    @commands.command(name="..")
    async def quote_show(self, ctx, *, trigger: str):
        'Show a quote'

        guild_group = self.config.guild(ctx.guild)

        async with guild_group.spam_channels() as spam_channels:
            if ctx.channel.id not in spam_channels:
                if await self.check_cooldown(ctx):
                    return

        trigger_data = await guild_group.quotes.trigger()
        triggers = None

        try:
            triggers = trigger_data[trigger]
        except KeyError:
            await ctx.send("Quote not found, add one `.. <trigger> <quote>`")
            return

        quote_id = random.choice(triggers)

        quotes = await guild_group.quotes.id()
        quote = quotes[str(quote_id)]["content"]
        await ctx.send(f"`#{quote_id}` :mega: {quote}")


    @commands.guild_only()
    @commands.command(name="qdel")
    async def quote_del(self, ctx, *, qid: str):
        'Delete a quote'

        guild_group = self.config.guild(ctx.guild)

        async with guild_group.quotes.id() as quotes, guild_group.quotes.trigger() as trigger_data:
            if qid not in quotes:
                await ctx.send(f"{ctx.author.mention}, invalid quote id.")
                return

            data = quotes[qid]

            # bandaid fix cause some user ids are strings, some are ints and some dont even exist
            if data["user"] != "":
                member = discord.utils.find(lambda m: m.id == int(data["user"]), ctx.channel.guild.members)
            else:
                member = None

            if ctx.author == member or ctx.author.guild_permissions.manage_messages:
                trigger = data["trigger"]
                del quotes[qid]
                trigger_data[trigger].remove(qid)

                await ctx.send(f"{ctx.author.mention} deleted quote #{qid}.")
                return

        await ctx.send(f"{ctx.author.mention}, only the creator (or admins) can delete that.")


    @commands.guild_only()
    @commands.command(name="qid")
    async def quote_info(self, ctx, *, qid: str):
        'Show details about a quote'

        guild_group = self.config.guild(ctx.guild)
        quotes = await guild_group.quotes.id()

        if qid not in quotes:
            await ctx.send(f"{ctx.author.mention}, invalid quote id.")
            return

        data = quotes[qid]

        # bandaid fix cause some user ids are strings, some are ints and some dont even exist
        if data["user"] != "":
            member = discord.utils.find(lambda m: m.id == int(data["user"]), ctx.channel.guild.members)
        else:
            member = None

        log = discord.Embed()
        log.type = "rich"

        log.set_author(name=member, url=data["jump_url"])
        log.title = f"Quote Info - #{qid}"

        created_at = datetime.datetime.fromtimestamp(data["datetime"])
        log.add_field(
            name=f"{data['trigger']}",
            value=f"{data['content']}",
            inline=False
        )
        log.add_field(
            name="Author",
            value=f"{member}",
        )
        log.add_field(
            name="Created",
            value=f"{created_at}",
        )

        await ctx.send(embed=log)


    @commands.guild_only()
    @commands.command(name="sadd")
    async def spam_channel_add(self, ctx):
        'Add a spam channel'

        if not ctx.author.guild_permissions.manage_channels:
            await ctx.send(f"{ctx.author.mention}, only users with manage_channels permissions can use this command.")
            return

        guild_group = self.config.guild(ctx.guild)

        async with guild_group.spam_channels() as spam_channels:
            if ctx.channel.id in spam_channels:
                await ctx.send(f"{ctx.channel.name} is already set as a spam channel.")
                return

            spam_channels.append(ctx.channel.id)

        await ctx.send(f"Successfully added {ctx.channel.name} as a spam channel.")


    @commands.guild_only()
    @commands.command(name="sdel")
    async def spam_channel_del(self, ctx):
        'Delete a spam channel'

        if not ctx.author.guild_permissions.manage_channels:
            await ctx.send(f"{ctx.author.mention}, only users with manage_channels permissions can use this command.")
            return

        guild_group = self.config.guild(ctx.guild)

        async with guild_group.spam_channels() as spam_channels:
            if ctx.channel.id not in spam_channels:
                await ctx.send(f"{ctx.channel.name} is not set as a spam channel.")
                return

            spam_channels.remove(ctx.channel.id)

        await ctx.send(f"Successfully removed {ctx.channel.name} from the spam channel list.")


    @commands.guild_only()
    @commands.command(name="tdel")
    async def quote_mass_del(self, ctx, *, trigger: str):
        'Mass delete quotes in a trigger (category)'

        if not ctx.author.guild_permissions.manage_messages:
            await ctx.send(f"{ctx.author.mention}, only admins can use this command.")
            return

        guild_group = self.config.guild(ctx.guild)

        async with guild_group.quotes.id() as quotes, guild_group.quotes.trigger() as trigger_data:
            try:
                triggers = trigger_data[trigger]
            except KeyError:
                await ctx.send("Trigger not found.")
                return

            quote_amount = len(triggers)

            for qid in triggers:
                del quotes[qid]

            del trigger_data[trigger]

        await ctx.send(f"{ctx.author.mention} deleted {quote_amount} quote(s).")


    @commands.guild_only()
    @commands.command(name="adel")
    async def author_quote_del(self, ctx, *, user_mention: str):
        'Mass delete quotes that a user added'

        if not ctx.author.guild_permissions.manage_messages:
            await ctx.send(f"{ctx.author.mention}, only admins can use this command.")
            return

        if len(ctx.message.raw_mentions) != 1:
            await ctx.send("Invalid use of command.")
            return

        mention_id = ctx.message.raw_mentions[0]

        guild_group = self.config.guild(ctx.guild)

        quote_amount = 0

        async with guild_group.quotes.id() as quotes, guild_group.quotes.trigger() as trigger_data:
            quote_ids = [x for x in quotes]

            for qid in quote_ids:

                # bandaid fix cause some user ids are string, some are ints and some dont even exist
                if str(quotes[qid]["user"]) != str(mention_id):
                    continue

                trigger = quotes[qid]["trigger"]

                del quotes[qid]
                trigger_data[trigger].remove(qid)
                quote_amount += 1

        await ctx.send(f"{ctx.author.mention} deleted {quote_amount} quote(s).")


    @commands.guild_only()
    @commands.command(name="qban")
    async def quote_ban(self, ctx, user_mention: str):
        'Ban a user from adding new quotes'

        if not ctx.author.guild_permissions.ban_members:
            await ctx.send(f"{ctx.author.mention}, only admins can use this command.")
            return

        if len(ctx.message.raw_mentions) != 1:
            await ctx.send("Invalid use of command.")
            return

        mention_id = ctx.message.raw_mentions[0]

        guild_group = self.config.guild(ctx.guild)

        async with guild_group.banlist() as banlist:
            if mention_id in banlist:
                await ctx.send("User is already banned.")
                return

            banlist.append(mention_id)

        await ctx.send(f"{ctx.author.mention} successfully banned <@{mention_id}>.")


    @commands.guild_only()
    @commands.command(name="qunban")
    async def quote_unban(self, ctx, user_mention):
        'Unban a user from adding new quotes'

        if not ctx.author.guild_permissions.ban_members:
            await ctx.send(f"{ctx.author.mention}, only admins can use this command.")
            return

        if len(ctx.message.raw_mentions) != 1:
            await ctx.send("Invalid use of command.")
            return

        mention_id = ctx.message.raw_mentions[0]

        guild_group = self.config.guild(ctx.guild)

        async with guild_group.banlist() as banlist:
            if mention_id not in banlist:
                await ctx.send("User is not banned.")
                return

            banlist.remove(mention_id)

        await ctx.send(f"{ctx.author.mention} successfully unbanned <@{mention_id}>.")
