import asyncio
import random
import sys
import time

from ew.backend import core as bknd_core
from ew.backend import hunting as bknd_hunt
from ew.backend import item as bknd_item
from ew.backend import worldevent as bknd_worldevent
from ew.backend.hunting import EwOperationData
from ew.backend.item import EwItem
from ew.backend.market import EwMarket
from ew.backend.status import EwEnemyStatusEffect
from ew.backend.status import EwStatusEffect
from ew.backend.worldevent import EwWorldEvent
from ew.static import cfg as ewcfg
from ew.static import hue as hue_static
from ew.static import items as static_items
from ew.static import mutations as static_mutations
from ew.static import poi as poi_static
from ew.static import status as se_static
from ew.static import vendors
from ew.static import weapons as static_weapons
from ew.utils import cmd as cmd_utils
from ew.utils import combat as cmbt_utils
from ew.utils import core as ewutils
from ew.utils import frontend as fe_utils
from ew.utils import hunting as hunt_utils
from ew.utils import item as itm_utils
from ew.utils import leaderboard as bknd_leaderboard
from ew.utils import prank as prank_utils
from ew.utils import rolemgr as ewrolemgr
from ew.utils import stats as ewstats
from ew.utils.combat import EwEnemy
from ew.utils.combat import EwUser
from ew.utils.district import EwDistrict
from ew.utils.frontend import EwResponseContainer
from ew.utils.slimeoid import EwSlimeoid
from .cmdsutils import exec_mutations
from .cmdsutils import gen_score_text
from .cmdsutils import get_user_shares_str
from .cmdsutils import item_commands
from .cmdsutils import item_off
from .cmdsutils import location_commands
from .cmdsutils import mutation_commands
from .. import item as ewitem
from ..apt import aptcmds as apt_cmds
from ..faction import factioncmds as faction_cmds
from ..wep import wepcmds as wep_cmds

""" show player's slime score """


async def score(cmd):
    time_now_cmd_start = int(time.time())
    user_data = None
    member = None
    skune = True if ewutils.flattenTokenListToString(cmd.tokens[0]) == 'skune' else False
    if len(cmd.mention_ids) == 0:
        target_type = "self"
    else:
        target_type = ewutils.mention_type(cmd, cmd.mention_ids[0])

    # endless war slime check
    if target_type == "ew":
        total = bknd_core.execute_sql_query("SELECT SUM(slimes) FROM users WHERE slimes > 0 AND id_server = '{}'".format(cmd.guild.id))
        totalslimes = total[0][0]
        response = "ENDLESS WAR has amassed {:,} slime.".format(totalslimes)

    # self slime check
    elif target_type == "self":
        user_data = EwUser(ew_id=cmd.author_id)
        poudrin_amount = bknd_item.find_poudrin(id_user=cmd.message.author.id, id_server=cmd.guild.id)

        # return my score
        response = "You currently have {:,} {}{}.".format(user_data.slimes, "slime" if skune is False else "skune", (" and {} {} poudrin{}".format(poudrin_amount, "slime" if skune is False else "skune", ("" if poudrin_amount == 1 else "s")) if poudrin_amount > 0 else ""))

    # other user slime check
    else:
        member = cmd.mentions[0]  # for ewrolemgr
        response = gen_score_text(ew_id=cmd.mention_ids[0], skune=skune)

    time_now_msg_start = int(time.time())
    # Send the response to the player.
    await fe_utils.send_response(response, cmd)
    time_now_msg_end = int(time.time())

    time_now_role_start = int(time.time())
    if member != None:  # update roles on other user slime check
        await ewrolemgr.updateRoles(client=cmd.client, member=member)
    time_now_role_end = int(time.time())

    time_now_cmd_end = int(time.time())


# ewutils.logMsg('send_response took {} seconds.'.format(time_now_msg_end - time_now_msg_start))
# ewutils.logMsg('updateRoles took {} seconds.'.format(time_now_role_end - time_now_role_start))
# ewutils.logMsg('total command time took {} seconds.'.format(time_now_cmd_end - time_now_cmd_start))

""" show player information and description """


async def data(cmd):
    member = None
    response = ""

    if len(cmd.mention_ids) == 0:
        target_type = "self"
    else:
        target_type = ewutils.mention_type(cmd, cmd.mention_ids[0])

    # enemy data check
    if len(cmd.tokens) > 1 and cmd.mentions_count == 0 and len(cmd.mention_ids) == 0:
        user_data = EwUser(member=cmd.message.author)

        soughtenemy = " ".join(cmd.tokens[1:]).lower()
        enemy = cmbt_utils.find_enemy(soughtenemy, user_data)
        if enemy != None:
            if enemy.attacktype != ewcfg.enemy_attacktype_unarmed:
                response = "{} is a level {} enemy. They have {:,} slime and attack with their {}. ".format(enemy.display_name, enemy.level, enemy.slimes, enemy.attacktype)
            else:
                response = "{} is a level {} enemy. They have {:,} slime".format(enemy.display_name, enemy.level, enemy.slimes)  # , enemy.hardened_sap)

            statuses = enemy.getStatusEffects()

            for status in statuses:
                status_effect = EwEnemyStatusEffect(id_status=status, enemy_data=enemy)
                if status_effect.time_expire > time.time() or status_effect.time_expire == -1:
                    status_flavor = se_static.status_effects_def_map.get(status)

                    severity = ""
                    try:
                        value_int = int(status_effect.value)
                        if value_int < 3:
                            severity = "lightly injured."
                        elif value_int < 7:
                            severity = "battered and bruised."
                        elif value_int < 11:
                            severity = "severely damaged."
                        else:
                            severity = "completely fucked up, holy shit!"
                    except:
                        pass

                    format_status = {'severity': severity}

                    if status_flavor is not None:
                        response += status_flavor.str_describe.format_map(format_status) + " "
        else:
            response = "ENDLESS WAR didn't understand that name."


    elif target_type == "ew":
        response = "ENDLESS WAR is a level 666 ancient obelisk. He is wielding THE BONE HURTING BEAM. He is a rank 111 bone hurter. He has been weathered by months of bicarbonate rain. He has millions of confirmed kills."


    # self data check
    elif target_type == "self":

        user_data = EwUser(member=cmd.message.author)
        slimeoid = EwSlimeoid(member=cmd.message.author)

        cosmetics = bknd_item.inventory(
            id_user=cmd.message.author.id,
            id_server=cmd.guild.id,
            item_type_filter=ewcfg.it_cosmetic
        )
        adorned_cosmetics = []

        for cosmetic in cosmetics:
            cos = EwItem(id_item=cosmetic.get('id_item'))
            if cos.item_props['adorned'] == 'true':
                hue = hue_static.hue_map.get(cos.item_props.get('hue'))
                adorned_cosmetics.append((hue.str_name + " " if hue != None else "") + cosmetic.get('name'))

        poi = poi_static.id_to_poi.get(user_data.poi)
        if poi != None:
            response = "You find yourself {} {}. ".format(poi.str_in, poi.str_name)


        #get race flavor text
        player_race = ewcfg.defined_races.get(user_data.race)
        if player_race != None:
            race_prefix = player_race.get("race_prefix", "")
            race_suffix = player_race.get("race_suffix", "")
        else:
            race_prefix = ""
            race_suffix = ""



        if user_data.life_state == ewcfg.life_state_corpse:
            response += "You are a {}level {} {}deadboi.".format(race_prefix, user_data.slimelevel, race_suffix)
        elif user_data.life_state == ewcfg.life_state_shambler:
            response += "You are a {}level {} {}shambler.".format(race_prefix, user_data.slimelevel, race_suffix)
        else:
            response += "You are a {}level {} {}slimeboi.".format(race_prefix, user_data.slimelevel, race_suffix)
            if user_data.degradation < 20:
                pass
            elif user_data.degradation < 40:
                response += " Your bodily integrity is starting to slip."
            elif user_data.degradation < 60:
                response += " Your face seems to be melting and you periodically have to put it back in place."
            elif user_data.degradation < 80:
                response += " You are walking a bit funny, because your legs are getting mushy."
            elif user_data.degradation < 100:
                response += " Your limbs keep falling off. It's really annoying."
            else:
                response += " You almost look like a shambler already."

        if user_data.has_soul == 0:
            response += " You have no soul."

        coinbounty = int(user_data.bounty / ewcfg.slimecoin_exchangerate)

        weapon_item = EwItem(id_item=user_data.weapon)
        weapon = static_weapons.weapon_map.get(weapon_item.item_props.get("weapon_type"))

        if weapon != None:
            response += " {} {}{}.".format(
                ewcfg.str_weapon_married_self if user_data.weaponmarried == True else ewcfg.str_weapon_wielding_self, (
                    "" if len(weapon_item.item_props.get("weapon_name")) == 0 else "{}, ".format(
                        weapon_item.item_props.get("weapon_name"))), weapon.str_weapon)
            if user_data.weaponskill >= 5:
                response += " {}".format(weapon.str_weaponmaster_self.format(rank=(user_data.weaponskill - 4), title="master"))
            else:
                response += " {}".format(weapon.str_weaponmaster_self.format(rank=(user_data.weaponskill), title="rookie"))

        trauma = se_static.trauma_map.get(user_data.trauma)

        sidearm_item = EwItem(id_item=user_data.sidearm)
        sidearm = static_weapons.weapon_map.get(sidearm_item.item_props.get("weapon_type"))

        if sidearm != None:
            response += " You have sidearmed {}{}.".format((
                "" if len(sidearm_item.item_props.get("weapon_name")) == 0 else "{}, ".format(
                    sidearm_item.item_props.get("weapon_name"))), sidearm.str_weapon)

        if trauma != None:
            response += " {}".format(trauma.str_trauma_self)

        response_block = ""

        user_kills = ewstats.get_stat(user=user_data, metric=ewcfg.stat_kills)
        enemy_kills = ewstats.get_stat(user=user_data, metric=ewcfg.stat_pve_kills)

        if user_kills > 0 and enemy_kills > 0:
            response_block += "You have {:,} confirmed kills, and {:,} confirmed hunts. ".format(user_kills,
                                                                                                 enemy_kills)
        elif user_kills > 0:
            response_block += "You have {:,} confirmed kills. ".format(user_kills)
        elif enemy_kills > 0:
            response_block += "You have {:,} confirmed hunts. ".format(enemy_kills)

        if coinbounty != 0:
            response_block += "SlimeCorp offers a bounty of {:,} SlimeCoin for your death. ".format(coinbounty)

        if len(adorned_cosmetics) > 0:
            response_block += "You have a {} adorned. ".format(ewutils.formatNiceList(adorned_cosmetics, 'and'))

            outfit_map = itm_utils.get_outfit_info(id_user=cmd.message.author.id, id_server=cmd.guild.id)
            user_data.persist()

            if outfit_map is not None:
                response_block += itm_utils.get_style_freshness_rating(user_data=user_data, dominant_style=outfit_map['dominant_style']) + " "

        if user_data.hunger > 0:
            response_block += "You are {}% hungry. ".format(
                round(user_data.hunger * 100.0 / user_data.get_hunger_max(), 1)
            )

        if user_data.busted and user_data.life_state == ewcfg.life_state_corpse:
            response_block += "You are busted and therefore cannot leave the sewers until your next !haunt. "

        statuses = user_data.getStatusEffects()

        for status in statuses:
            status_effect = EwStatusEffect(id_status=status, user_data=user_data)
            if status_effect.time_expire > time.time() or status_effect.time_expire == -1:
                status_flavor = se_static.status_effects_def_map.get(status)

                severity = ""
                try:
                    value_int = int(status_effect.value)
                    if value_int < 3:
                        severity = "lightly injured."
                    elif value_int < 7:
                        severity = "battered and bruised."
                    elif value_int < 11:
                        severity = "severely damaged."
                    else:
                        severity = "completely fucked up, holy shit!"
                except:
                    pass

                format_status = {'severity': severity}

                if status_flavor is not None:
                    response_block += status_flavor.str_describe_self.format_map(format_status) + " "

        if (slimeoid.life_state == ewcfg.slimeoid_state_active) and (user_data.life_state != ewcfg.life_state_corpse):
            response_block += "You are accompanied by {}, a {}-foot-tall Slimeoid. ".format(slimeoid.name, str(slimeoid.level))

        server = ewutils.get_client().get_guild(user_data.id_server)
        if user_data.life_state == ewcfg.life_state_corpse:
            inhabitee_id = user_data.get_inhabitee()
            if inhabitee_id:
                inhabitee_name = server.get_member(inhabitee_id).display_name
                possession = user_data.get_possession()
                if possession:
                    if possession[3] == 'weapon':
                        response_block += "You are currently possessing {}'s weapon. ".format(inhabitee_name)
                    elif possession[3] == 'rod':
                        response_block += "You are currently possessing {}'s fishing rod. ".format(inhabitee_name)
                else:
                    response_block += "You are currently inhabiting the body of {}. ".format(inhabitee_name)
        else:
            inhabitant_ids = user_data.get_inhabitants()
            if inhabitant_ids:
                inhabitant_names = []
                for inhabitant_id in inhabitant_ids:
                    inhabitant_names.append(server.get_member(inhabitant_id).display_name)

                possession = user_data.get_possession()
                if possession is not None:
                    ghost_in_weapon = possession[0]
                    possession_type = 'fishing rod' if possession[3] == 'rod' else possession[3]

                if len(inhabitant_names) == 1:
                    response_block += "You are inhabited by the ghost of {}{}. ".format(inhabitant_names[0], ', who is possessing your ' + possession_type if possession else '')
                else:
                    response_block += "You are inhabited by the ghosts of {}{} and {}. ".format(
                        ", ".join(inhabitant_names[:-1]),
                        "" if len(inhabitant_names) == 2 else ",",
                        inhabitant_names[-1]
                    )
                    if possession:
                        response_block += "{} is also possessing your {}. ".format(server.get_member(ghost_in_weapon).display_name, possession_type)

        # if user_data.swear_jar >= 500:
        # 	response_block += "You're going to The Underworld for the things you've said."
        # elif user_data.swear_jar >= 100:
        # 	response_block += "You swear like a sailor!"
        # elif user_data.swear_jar >= 50:
        # 	response_block += "You have quite a profane vocabulary."
        # elif user_data.swear_jar >= 10:
        # 	response_block += "You've said some naughty things in the past."
        # elif user_data.swear_jar >= 5:
        # 	response_block += "You've cussed a handful of times here and there."
        # elif user_data.swear_jar > 0:
        # 	response_block += "You've sworn only a few times."
        # else:
        # 	response_block += "Your mouth is clean as a whistle."

        if len(response_block) > 0:
            response += "\n" + response_block

        response += "\n\nhttps://ew.krakissi.net/stats/player.html?pl={}".format(user_data.id_user)

    # other data check
    else:
        member = cmd.mentions[0]
        response = cmd_utils.gen_data_text(
            id_user=member.id,
            id_server=member.guild.id,
            display_name=member.display_name,
            channel_name=cmd.message.channel.name
        )

        response += "\n\nhttps://ew.krakissi.net/stats/player.html?pl={}".format(member.id)

    # Send the response to the player.
    await fe_utils.send_response(response, cmd)

    await ewrolemgr.updateRoles(client=cmd.client, member=cmd.message.author)
    if member != None:
        await ewrolemgr.updateRoles(client=cmd.client, member=member)


""" Finally, separates mutations from !data """


async def mutations(cmd):
    response = ""
    total_levels = 0

    if "level" in cmd.tokens:
        response += "\n"

    if cmd.mentions_count == 0:
        user_data = EwUser(member=cmd.message.author)
        mutations = user_data.get_mutations()

        if user_data.life_state in [ewcfg.life_state_executive, ewcfg.life_state_lucky]:
            return await exec_mutations(cmd)

        for mutation in mutations:
            mutation_flavor = static_mutations.mutations_map[mutation]
            total_levels += mutation_flavor.tier
            if "level" in cmd.tokens:
                response += "**LEVEL {}**:{} \n".format(mutation_flavor.tier, mutation_flavor.str_describe_self)
            else:
                response += "{} ".format(mutation_flavor.str_describe_self)
        if len(mutations) == 0:
            response = "You are miraculously unmodified from your normal genetic code!"
        elif "level" in cmd.tokens:
            response += "Total Levels: {}/50\nMutation Levels Added: {}/{}".format(user_data.slimelevel, total_levels, min(50, user_data.slimelevel))

    else:
        member = cmd.mentions[0]
        user_data = EwUser(
            id_user=member.id,
            id_server=member.guild.id
        )
        if user_data.life_state in [ewcfg.life_state_executive, ewcfg.life_state_lucky]:
            return await exec_mutations(cmd)

        mutations = user_data.get_mutations()
        for mutation in mutations:
            mutation_flavor = static_mutations.mutations_map[mutation]
            total_levels += mutation_flavor.tier
            if "level" in cmd.tokens:
                response += "**LEVEL {}**:{} \n".format(mutation_flavor.tier, mutation_flavor.str_describe_other)
            else:
                response += "{} ".format(mutation_flavor.str_describe_other)
        if len(mutations) == 0:
            response = "They are miraculously unmodified from their normal genetic code!"
        elif "level" in cmd.tokens:
            response += "Total Levels: {}/50\nMutation Levels Added: {}/{}".format(user_data.slimelevel, total_levels, min(50, user_data.slimelevel))
    await fe_utils.send_response(response, cmd)


""" Check how hungry you are. """


async def hunger(cmd):
    user_data = EwUser(member=cmd.message.author)
    response = ""

    if user_data.hunger > 0:
        response = "You are {}% hungry. ".format(
            round(user_data.hunger * 100.0 / user_data.get_hunger_max(), 1)
        )
    else:
        response = "You aren't hungry at all."

    return await fe_utils.send_response(response, cmd)


""" time and weather information """


async def weather(cmd):
    market_data = EwMarket(id_server=cmd.guild.id)
    response = ewutils.weather_txt(market_data)

    time_current = market_data.clock
    if 3 <= time_current <= 10:
        response += "\n\nThe police are probably all asleep, the lazy fucks. It's a good time for painting the town!"
    # Send the response to the player.
    await fe_utils.send_response(response, cmd)


"""
	Killers DAB
"""


async def dab(cmd):
    user_data = EwUser(member=cmd.message.author)

    if (user_data.life_state == ewcfg.life_state_enlisted or user_data.life_state == ewcfg.life_state_kingpin) and user_data.faction == ewcfg.faction_killers:
        response = '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_ck + ewcfg.emote_slime3 + ewcfg.emote_slime1 + ewcfg.emote_slime3 + ewcfg.emote_slime3 + ewcfg.emote_ck + ewcfg.emote_slime3 + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_slime1 + ewcfg.emote_ck + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_slime1 + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_slime3 + ewcfg.emote_ck + ewcfg.emote_slime3 + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + '\n' + ewcfg.emote_copkiller + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_slime3 + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_slime1 + ewcfg.emote_slime1 + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_copkiller + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_slime1 + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_slime3 + ewcfg.emote_ck + ewcfg.emote_slime3 + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_ck + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_ck + ewcfg.emote_slime3 + ewcfg.emote_slime1 + ewcfg.emote_slime1 + ewcfg.emote_slime3 + ewcfg.emote_ck + ewcfg.emote_slime1 + ewcfg.emote_ck + ewcfg.emote_ck + ewcfg.emote_slime1 + ewcfg.emote_ck
        await fe_utils.send_response(response, cmd)


"""
	Rowdys THRASH
"""


async def thrash(cmd):
    user_data = EwUser(member=cmd.message.author)

    if (user_data.life_state == ewcfg.life_state_enlisted or user_data.life_state == ewcfg.life_state_kingpin) and user_data.faction == ewcfg.faction_rowdys:
        response = '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_rf + ewcfg.emote_slime3 + ewcfg.emote_slime1 + ewcfg.emote_slime3 + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_slime1 + ewcfg.emote_slime1 + ewcfg.emote_slime3 + ewcfg.emote_slime1 + ewcfg.emote_rf + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_slime1 + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_slime1 + ewcfg.emote_rf + ewcfg.emote_slime3 + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf + '\n' + ewcfg.emote_rowdyfucker + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_slime3 + ewcfg.emote_slime1 + ewcfg.emote_slime3 + ewcfg.emote_slime1 + ewcfg.emote_rf + ewcfg.emote_slime3 + ewcfg.emote_slime1 + ewcfg.emote_slime1 + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rowdyfucker + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_slime1 + ewcfg.emote_rf + ewcfg.emote_slime3 + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_slime3 + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_rf + ewcfg.emote_slime1 + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_slime1 + ewcfg.emote_rf + ewcfg.emote_slime1 + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf + ewcfg.emote_rf
        await fe_utils.send_response(response, cmd)


"""
	Ghosts BOO
"""


async def boo(cmd):
    user_data = EwUser(member=cmd.message.author)

    if user_data.life_state == ewcfg.life_state_corpse or user_data.life_state == ewcfg.life_state_grandfoe:
        resp_cont = EwResponseContainer(id_server=user_data.id_server)

        response = '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_staydead + ewcfg.emote_srs + ewcfg.emote_negaslime + ewcfg.emote_negaslime + ewcfg.emote_srs + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_negaslime + ewcfg.emote_srs + ewcfg.emote_staydead + ewcfg.emote_staydead + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_srs + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + '\n' + ewcfg.emote_ghost + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_negaslime + ewcfg.emote_srs + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_srs + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_ghost + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_srs + ewcfg.emote_negaslime + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_srs + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead
        await fe_utils.send_response(response, cmd)
    # resp_cont.add_channel_response(cmd.message.channel.name, response)
    # if user_data.life_state == ewcfg.life_state_corpse or user_data.life_state == ewcfg.life_state_grandfoe:
    # await resp_cont.post()


# await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_staydead + ewcfg.emote_srs + ewcfg.emote_negaslime + ewcfg.emote_negaslime + ewcfg.emote_srs + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_negaslime + ewcfg.emote_srs + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_blank + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_srs + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_blank + ewcfg.emote_blank + '\n' + ewcfg.emote_ghost + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_negaslime + ewcfg.emote_srs + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_srs + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_ghost + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_blank + ewcfg.emote_blank + '\n' + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_srs + ewcfg.emote_negaslime + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_negaslime + ewcfg.emote_srs + ewcfg.emote_negaslime + ewcfg.emote_staydead + ewcfg.emote_staydead + ewcfg.emote_blank + ewcfg.emote_blank + ewcfg.emote_blank))


async def spook(cmd):
    # user_data = EwUser(member=cmd.message.author)
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, '\n' "***SPOOKED YA!***" + '\n' + "https://www.youtube.com/watch?v=T-dtcIXZo4s"))


"""
	Juvies DANCE
"""


async def dance(cmd):
    user_data = EwUser(ew_id=cmd.author_id)

    if user_data.life_state == ewcfg.life_state_juvenile or user_data.life_state == ewcfg.life_state_shambler:
        response = random.choice(ewcfg.dance_responses).format(cmd.author_id.display_name)
        response = "{} {} {}".format(ewcfg.emote_slime3, response, ewcfg.emote_slime3)
        await fe_utils.send_response(response, cmd, format_name=False)


"""
	Slimecorp PROPAGANDIZES
"""


async def propaganda(cmd):
    user_data = EwUser(ew_id=cmd.author_id)

    if (user_data.life_state == ewcfg.life_state_enlisted and user_data.faction == ewcfg.faction_slimecorp) or user_data.life_state == ewcfg.life_state_executive:
        response = random.choice("ur bad")
        await fe_utils.send_response(response, cmd)


"""
	Terezi Gang FLIP COINS
"""


async def coinflip(cmd):
    user_data = EwUser(member=cmd.message.author)
    response = ""

    if fe_utils.check_user_has_role(cmd.guild, cmd.message.author, ewcfg.role_donor_proper):

        if user_data.slimecoin <= 1:
            return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "YOU DON'T H4V3 4NY SL1M3CO1N TO FL1P >:["))
        else:
            user_data.change_slimecoin(n=-1, coinsource=ewcfg.coinsource_spending)
            user_data.persist()

        await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "YOU FL1P ON3 SL1M3CO1N R1GHT 1N TH3 41R!\nhttps://cdn.discordapp.com/attachments/431240644464214017/652341405129375794/Terezi_Hussnasty_coinflip.gif"))
        await asyncio.sleep(2)
        await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "..."))
        await asyncio.sleep(3)

        flipnum = random.randrange(2)

        if flipnum == 0:
            response = "H34DS!\nhttps://www.homestuck.com/images/storyfiles/hs2/02045_3.gif"
        else:
            response = "T41LS!\nhttps://66.media.tumblr.com/tumblr_m6gdpg4qOg1r6ajb6.gif"

        await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


"""
    Bass weilders JAM OUT
"""


async def jam(cmd):
    # def leppard and pearl jam? meet def jam. this is what the refrance, fuck yeah.
    item_found = ewutils.flattenTokenListToString(cmd.tokens[1:])
    item_sought = bknd_item.find_item(item_search=item_found, id_user=cmd.message.author.id, id_server=cmd.guild.id)

    if item_sought:
        item = EwItem(id_item=item_sought.get('id_item'))
        if item.item_props.get("id_furniture") in static_items.furniture_instrument or item.item_props.get("weapon_type") == ewcfg.weapon_id_bass:
            cycle = random.randrange(20)
            response = ""
            if random.randint(0, 10) == 0:
                if item.item_props.get("id_furniture") == None:
                    item_key = "bass"
                else:
                    item_key = item.item_props.get("id_furniture")
                response = random.choice(ewcfg.jam_tunes[item_key])
            else:
                for x in range(1, cycle):
                    response += random.choice([":musical_note:", ":notes:"])
        else:
            response = "You place your mouth on the {} but it makes no noise. Either that's not an instrument or you aren't good enough.".format(item_sought.get('name'))
    else:
        response = "Are you sure you have that item?"

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def endlesswar(cmd):
    total = bknd_core.execute_sql_query("SELECT SUM(slimes) FROM users WHERE slimes > 0 AND id_server = '{}'".format(cmd.guild.id))
    totalslimes = total[0][0]
    response = "ENDLESS WAR has amassed {:,} slime.".format(totalslimes)
    return await fe_utils.send_response(response, cmd)


async def slimefest(cmd):
    market_data = EwMarket(id_server=cmd.guild.id)

    response = "Soon..."
    # if market_data.winner == ewcfg.faction_killers:
    #	response = "Killers are winning Slimefest."
    # elif market_data.winner == ewcfg.faction_rowdys:
    #	response = "Rowdys are winning Slimefest."

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def swearjar(cmd):
    market_data = EwMarket(id_server=cmd.guild.id)
    total_swears = market_data.global_swear_jar

    response = "The swear jar has reached: **{}**".format(total_swears)

    if total_swears < 1000:
        pass
    elif total_swears < 10000:
        response += "\nThings are starting to get nasty."
    elif total_swears < 100000:
        response += "\nSwears? In *my* free Text-Based MMORPG playable entirely within my browser? It's more likely than you think."
    elif total_swears < 1000000:
        response += "\nGod help us all..."
    else:
        response = "\nThe city is rife with mischief and vulgarity, though that's hardly a surprise when it's inhabited by lowlifes and sinners across the board."

    return await fe_utils.send_response(response, cmd)


async def toss_off_cliff(cmd):
    user_data = EwUser(member=cmd.message.author)
    item_search = ewutils.flattenTokenListToString(cmd.tokens[1:])
    item_sought = bknd_item.find_item(item_search=item_search, id_user=cmd.message.author.id, id_server=user_data.id_server)

    if cmd.message.channel.name != ewcfg.channel_slimesendcliffs:
        if item_sought:
            if item_sought.get('name') == "brick" and cmd.mentions_count > 0:
                item = EwItem(id_item=item_sought.get('id_item'))
                target = EwUser(member=cmd.mentions[0])
                if target.apt_zone == user_data.poi:
                    item.id_owner = str(cmd.mentions[0].id) + ewcfg.compartment_id_decorate
                    item.persist()
                    response = "You throw a brick through {}'s window. Oh shit! Quick, scatter before they see you!".format(cmd.mentions[0].display_name)
                    if poi_static.id_to_poi.get(target.poi).is_apartment and target.visiting == ewcfg.location_id_empty:
                        try:
                            await fe_utils.send_message(cmd.client, cmd.mentions[0], fe_utils.formatMessage(cmd.mentions[0], "SMAAASH! A brick flies through your window!"))
                        except:
                            ewutils.logMsg("failed to send brick message to user {}".format(target.id_user))
                elif target.poi == user_data.poi:
                    if target.life_state == ewcfg.life_state_corpse:
                        response = "You reel back and chuck the brick at a ghost. As much as we both would like to teach the dirty staydead a lesson, the brick passes right through."
                        item.id_owner = target.poi
                        item.persist()
                    elif target.life_state == ewcfg.life_state_shambler:
                        response = "The brick is buried into the shambler's soft, malleable head, but the decayed fellow doesn't seem to notice. It looks like it phased into its inventory."
                        item.id_owner = target.id_user
                        item.persist()
                    elif target.life_state == ewcfg.life_state_kingpin:
                        response = "The brick is hurtling toward the kingpin's head, but they've long since gotten used to bricks to the head. It bounces off like nothing."
                        item.id_owner = target.poi
                        item.persist()
                    else:
                        response = ":bricks::boom: BONK! The brick slams against {}'s head!".format(cmd.mentions[0].display_name)
                        item.id_owner = target.poi
                        item.persist()
                        try:
                            await fe_utils.send_message(cmd.client, cmd.mentions[0], fe_utils.formatMessage(cmd.mentions[0], random.choice(["!!!!!!", "BRICK!", "FUCK", "SHIT", "?!?!?!?!?", "BONK!", "F'TAAAAANG!", "SPLAT!", "SPLAPP!", "WHACK"])))
                        except:
                            ewutils.logMsg("failed to send brick message to user {}".format(target.id_user))
                else:
                    response = "There's nobody here."
                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
            else:
                return await ewitem.itemcmds.discard(cmd=cmd)
        else:
            response = "You don't have that item."
            return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    elif item_sought:
        item_obj = EwItem(id_item=item_sought.get('id_item'))
        if item_obj.soulbound == True:
            response = "That's soulbound. You can't get rid of it just because you're in a more dramatic looking place."

        elif item_obj.item_type == ewcfg.it_weapon and user_data.weapon >= 0 and item_obj.id_item == user_data.weapon:
            if user_data.weaponmarried:
                weapon = static_weapons.weapon_map.get(item_obj.item_props.get("weapon_type"))
                response = "You decide not to chuck your betrothed off the cliff because you care about them very very much. See {}? I'm not going to hurt you. You don't have to call that social worker again.".format(weapon.str_weapon)
                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

            else:
                response = item_off(item_sought.get('id_item'), user_data.id_server, item_sought.get('name'))
            return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
        else:
            response = item_off(item_sought.get('id_item'), user_data.id_server, item_sought.get('name'))
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    else:
        response = "You don't have that item."
        await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def jump(cmd):
    user_data = EwUser(member=cmd.message.author)

    if user_data.poi in [ewcfg.poi_id_mine, ewcfg.poi_id_cv_mines, ewcfg.poi_id_tt_mines]:
        response = "You bonk your head on the shaft's ceiling."
        # if voidhole world event is valid, move the guy to the void and post a message
        # else, post something about them bonking their heads
        world_events = bknd_worldevent.get_world_events(id_server=cmd.guild.id)
        for id_event in world_events:
            if world_events.get(id_event) == ewcfg.event_type_voidhole:
                event_data = EwWorldEvent(id_event=id_event)
                if int(event_data.event_props.get('id_user')) == user_data.id_user and event_data.event_props.get('poi') == user_data.poi:
                    response = "You jump in!"
                    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                    await asyncio.sleep(1)

                    user_data.poi = ewcfg.poi_id_thevoid
                    user_data.time_lastenter = int(time.time())
                    user_data.persist()
                    await user_data.move_inhabitants(id_poi=ewcfg.poi_id_thevoid)
                    await ewrolemgr.updateRoles(client=cmd.client, member=cmd.message.author)

                    void_poi = poi_static.id_to_poi.get(ewcfg.poi_id_thevoid)
                    wafflehouse_poi = poi_static.id_to_poi.get(ewcfg.poi_id_thevoid)
                    response = "You do a backflip on the way down, bounce on the trampoline a few times to reduce your momentum, and climb down a ladder from the roof, down to the ground. You find yourself standing next to {}, in {}.".format(wafflehouse_poi.str_name, void_poi.str_name)
                    await fe_utils.send_message(cmd.client, fe_utils.get_channel(cmd.guild, void_poi.channel), fe_utils.formatMessage(cmd.message.author, response), 20)
                    # await asyncio.sleep(20)
                    # try:
                    # await msg.delete()
                    # pass
                    # except:
                    # pass
                    return

    elif cmd.message.channel.name != ewcfg.channel_slimesendcliffs:
        roll = random.randrange(25)
        if roll == 0:
            response = "You start running and taking momentum to then make the fucking highest jump you've ever done. When you reach the ground, you somehow manage to do a sommersault landing. Damn, guess you were good at parkour in the end!"
        else:
            response = "You jump. Nope. Still not good at parkour."
    elif user_data.life_state == ewcfg.life_state_corpse:
        response = "You're already dead. You'd just ghost hover above the cliff."
    elif user_data.life_state == ewcfg.life_state_kingpin:
        response = "You try to end things right here. Sadly, the gangster sycophants that kiss the ground you walk on grab your ankles in desperation and prevent you from suicide. Oh, the price of fame."
    else:
        response = "Hmm. The cliff looks safe enough. You imagine, with the proper diving posture, you'll be able to land in the slime unharmed. You steel yourself for the fall, run along the cliff, and swan dive off its steep edge. Of course, you forgot that the Slime Sea is highly corrosive, there are several krakens there, and you can't swim. Welp, time to die."

        cliff_inventory = bknd_item.inventory(id_server=cmd.guild.id, id_user=user_data.id_user)
        for item in cliff_inventory:
            item_object = EwItem(id_item=item.get('id_item'))
            if item.get('soulbound') == True:
                pass

            elif item_object.item_type == ewcfg.it_weapon:
                if item.get('id_item') == user_data.weapon or item.get('id_item') == user_data.sidearm:
                    bknd_item.give_item(id_item=item_object.id_item, id_user=ewcfg.poi_id_slimesea, id_server=cmd.guild.id)

                else:
                    item_off(id_item=item.get('id_item'), is_pushed_off=True, item_name=item.get('name'), id_server=cmd.guild.id)


            elif item_object.item_props.get('adorned') == 'true':
                bknd_item.give_item(id_item=item_object.id_item, id_user=ewcfg.poi_id_slimesea, id_server=cmd.guild.id)

            else:
                item_off(id_item=item.get('id_item'), is_pushed_off=True, item_name=item.get('name'), id_server=cmd.guild.id)

        user_data.trauma = ewcfg.trauma_id_environment
        die_resp = user_data.die(cause=ewcfg.cause_cliff)
        user_data.persist()
        await ewrolemgr.updateRoles(client=cmd.client, member=cmd.message.author)
        if die_resp != EwResponseContainer(id_server=cmd.guild.id):
            await die_resp.post()
    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def push(cmd):
    time_now = int(time.time())
    user_data = EwUser(member=cmd.message.author)
    districtmodel = EwDistrict(id_server=cmd.guild.id, district=ewcfg.poi_id_slimesendcliffs)

    if cmd.mentions_count == 0:
        response = "You try to push a nearby building. Nope, still not strong enough to move it."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
    elif cmd.mentions_count >= 2:
        response = "You can't push more than one person at a time."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    target = cmd.mentions[0]
    targetmodel = EwUser(member=target)
    target_mutations = targetmodel.get_mutations()
    user_mutations = user_data.get_mutations()

    server = cmd.guild

    if targetmodel.poi != user_data.poi:
        response = "You can't {} them because they aren't here.".format(cmd.tokens[0])

    elif cmd.message.channel.name != ewcfg.channel_slimesendcliffs:
        response = random.choice(ewcfg.bully_responses)

        formatMap = {}
        formatMap["target_name"] = target.display_name

        slimeoid_model = EwSlimeoid(id_server=cmd.guild.id, id_user=targetmodel.id_user)
        if slimeoid_model.name != "":
            slimeoid_model = slimeoid_model.name
        else:
            slimeoid_model = ""

        cosmetics = bknd_item.inventory(id_user=targetmodel.id_user, id_server=targetmodel.id_server, item_type_filter=ewcfg.it_cosmetic)
        selected_cos = None
        for cosmetic in cosmetics:
            cosmetic_item = EwItem(id_item=cosmetic.get('id_item'))
            if cosmetic_item.item_props.get('adorned') == "true":
                selected_cos = cosmetic
                break

        if selected_cos == None:
            selected_cos = "PANTS"
        else:
            selected_cos = id_item = selected_cos.get('name')

        formatMap["cosmetic"] = selected_cos.upper()

        if "{slimeoid}" in response:
            if slimeoid_model != "":
                formatMap["slimeoid"] = slimeoid_model
            elif slimeoid_model == "":
                response = "You push {target_name} into a puddle of sludge, laughing at how hopelessly dirty they are."

        response = response.format_map(formatMap)

    elif targetmodel.id_user == user_data.id_user:
        response = "You can't push yourself you FUCKING IDIOT!"

    elif user_data.life_state == ewcfg.life_state_corpse:
        response = "You attempt to push {} off the cliff, but your hand passes through them. If you're going to push someone, make sure you're corporeal.".format(target.display_name)

    elif targetmodel.life_state == ewcfg.life_state_corpse:
        response = "You try to give ol' {} a shove, but they're a bit too dead to be taking up physical space.".format(target.display_name)

    # elif time_now > targetmodel.time_expirpvp:
    # Target is not flagged for PvP.
    #	response = "{} is not mired in the ENDLESS WAR right now.".format(target.display_name)

    elif (ewcfg.mutation_id_bigbones in target_mutations or ewcfg.mutation_id_fatchance in target_mutations) and (ewcfg.mutation_id_lightasafeather not in target_mutations and ewcfg.mutation_id_airlock not in target_mutations):
        response = "You try to push {}, but they're way too heavy. It's always fat people, constantly trying to prevent your murderous schemes.".format(target.display_name)

    elif targetmodel.life_state == ewcfg.life_state_kingpin:
        response = "You sneak behind the kingpin and prepare to push. The crime you're about to commit is so heinous that you start snickering to yourself, and {} catches you in the act. Shit, mission failed.".format(target.display_name)

    elif ewcfg.mutation_id_lightasafeather in user_mutations or ewcfg.mutation_id_airlock in user_mutations:
        response = "You strain to push {} off the cliff, but your light frame gives you no lifting power.".format(target.display_name)

    else:
        response = "You push {} off the cliff and watch them scream in agony as they fall. Sea monsters frenzy on their body before they even land, gnawing them to jagged ribbons and gushing slime back to the clifftop.".format(target.display_name)

        if ewcfg.mutation_id_lightasafeather in target_mutations or ewcfg.mutation_id_airlock in target_mutations:
            response = "You pick {} up with your thumb and index finger, and gently toss them off the cliff. Wow. That was easy.".format(target.display_name)

        slimetotal = targetmodel.slimes * 0.75
        districtmodel.change_slimes(n=slimetotal)
        districtmodel.persist()

        cliff_inventory = bknd_item.inventory(id_server=cmd.guild.id, id_user=targetmodel.id_user)
        for item in cliff_inventory:
            item_object = EwItem(id_item=item.get('id_item'))
            if item.get('soulbound') == True:
                pass

            elif item_object.item_type == ewcfg.it_weapon:
                if item.get('id_item') == targetmodel.weapon:
                    bknd_item.give_item(id_item=item_object.id_item, id_user=ewcfg.poi_id_slimesea, id_server=cmd.guild.id)

                else:
                    item_off(id_item=item.get('id_item'), is_pushed_off=True, item_name=item.get('name'), id_server=cmd.guild.id)


            elif item_object.item_props.get('adorned') == 'true':
                bknd_item.give_item(id_item=item_object.id_item, id_user=ewcfg.poi_id_slimesea, id_server=cmd.guild.id)

            else:
                item_off(id_item=item.get('id_item'), is_pushed_off=True, item_name=item.get('name'), id_server=cmd.guild.id)

        targetmodel.trauma = ewcfg.trauma_id_environment
        die_resp = targetmodel.die(cause=ewcfg.cause_cliff)
        targetmodel.persist()

        user_data.persist()

        await ewrolemgr.updateRoles(client=cmd.client, member=target)
        await ewrolemgr.updateRoles(client=cmd.client, member=cmd.message.author)

        await die_resp.post()

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def purify(cmd):
    user_data = EwUser(member=cmd.message.author)
    if user_data.life_state == ewcfg.life_state_shambler:
        response = "You lack the higher brain functions required to {}.".format(cmd.tokens[0])
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if user_data.poi == ewcfg.poi_id_sodafountain:
        poi = poi_static.id_to_poi.get(user_data.poi)
        district_data = EwDistrict(district=poi.id_poi, id_server=user_data.id_server)

        if district_data.is_degraded():
            response = "{} has been degraded by shamblers. You can't {} here anymore.".format(poi.str_name, cmd.tokens[0])
            return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
        if user_data.life_state == ewcfg.life_state_corpse:
            response = "You're too ghastly for something like that. Besides, you couldn't even touch the water if you wanted to, it would just phase right through your ghostly form."
        else:
            if user_data.slimelevel < 50:
                response = "You're not big enough in slime levels to be worthy of purification"
            else:
                response = "You close your eyes and hold out your hands to the gentle waters of the bicarbonate soda fountain..."

                user_data.slimelevel = 1
                user_data.slimes = 0
                # user_data.hardened_sap = 0

                new_weaponskill = int(user_data.weaponskill * 0.75)

                ewutils.weaponskills_clear(id_server=user_data.id_server, id_user=user_data.id_user, weaponskill=new_weaponskill)

                user_data.persist()

                response += "\n\nYou have purified yourself and are now a level 1 slimeboi.\nThe bond you've forged with your weapon has grown weaker as a result."
    else:
        response = "Purify yourself how? With what? Your own piss?"

    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def store_item(cmd):
    user_data = EwUser(member=cmd.message.author)
    poi = poi_static.id_to_poi.get(user_data.poi)

    if poi.community_chest != None:
        return await faction_cmds.store(cmd)
    elif poi.is_apartment:
        return await apt_cmds.store_item(cmd)
    # response = "Try that in a DM to ENDLESS WAR."
    else:
        response = "There is no storage here, public or private."
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def remove_item(cmd):
    user_data = EwUser(member=cmd.message.author)
    poi = poi_static.id_to_poi.get(user_data.poi)

    if poi.community_chest != None:
        return await faction_cmds.take(cmd)
    elif poi.is_apartment:
        return await apt_cmds.remove_item(cmd)
    # response = "Try that in a DM to ENDLESS WAR."
    else:
        response = "There is no storage here, public or private."
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def check_flag(cmd):
    response = "https://img.booru.org/rfck//images/2/5c00b9d105d2435546ff6d3d9f545b05650d6631.png"
    return await fe_utils.send_message(cmd.client, cmd.message.channel, response)
    """
    user_data = EwUser(member=cmd.message.author)
    poi = poi_static.id_to_poi.get(user_data.poi)

    if user_data.time_expirpvp < int(time.time()):
        response = "You don't have a flag."
    else:
        response = "You have {:,} seconds left on your flag.".format(abs(user_data.time_expirpvp - int(time.time())))

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


    """


""" Accept a russian roulette challenge """


async def accept(cmd):
    user = EwUser(member=cmd.message.author)
    if (ewutils.active_target_map.get(user.id_user) != None and ewutils.active_target_map.get(user.id_user) != ""):
        challenger = EwUser(id_user=ewutils.active_target_map[user.id_user], id_server=user.id_server)
        if (ewutils.active_target_map.get(user.id_user) != user.id_user and ewutils.active_target_map.get(challenger.id_user) != user.id_user):
            ewutils.active_target_map[challenger.id_user] = user.id_user
            slimeoid_data = EwSlimeoid(member=cmd.message.author)
            response = ""
            if user.poi == ewcfg.poi_id_arena and ewutils.active_slimeoidbattles.get(slimeoid_data.id_slimeoid):
                response = "You accept the challenge! Both of your Slimeoids ready themselves for combat!"
            elif user.poi == ewcfg.poi_id_thecasino and ewutils.active_restrictions[challenger.id_user] == 1:
                response = "You accept the challenge! Both of you head out back behind the casino and load a bullet into the gun."

            if len(response) > 0:
                await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


""" Refuse a russian roulette challenge """


async def refuse(cmd):
    user = EwUser(member=cmd.message.author)

    if (ewutils.active_target_map.get(user.id_user) != None and ewutils.active_target_map.get(user.id_user) != ""):
        challenger = EwUser(id_user=ewutils.active_target_map[user.id_user], id_server=user.id_server)

        ewutils.active_target_map[user.id_user] = ""
        ewutils.active_restrictions[user.id_user] = 0

        if (ewutils.active_target_map.get(user.id_user) != user.id_user and ewutils.active_target_map.get(challenger.id_user) != user.id_user):
            response = "You refuse the challenge, but not before leaving a large puddle of urine beneath you."
            await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
        else:
            ewutils.active_target_map[challenger.id_user] = ""
            ewutils.active_restrictions[challenger.id_user] = 0


async def confirm(cmd):
    return


async def cancel(cmd):
    return


"""
	Link to the world map.
"""


async def map(cmd):
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, 'Online world map: https://ew.krakissi.net/map/'))


"""
	Link to the subway map
"""


async def transportmap(cmd):
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author,
                                                                                        "Map of the subway: https://cdn.discordapp.com/attachments/431238867459375145/570392908780404746/t_system_final_stop_telling_me_its_wrong_magicks.png\nPlease note that there also exists a **blimp** that goes between Dreadford and Assault Flats Beach, as well as a **ferry** that goes between Wreckington and Vagrant's Corner."))


""" Check your outfit. """


async def fashion(cmd):
    if cmd.mentions_count == 0:
        user_data = EwUser(member=cmd.message.author, data_level=2)

        cosmetic_items = bknd_item.inventory(
            id_user=cmd.message.author.id,
            id_server=cmd.guild.id,
            item_type_filter=ewcfg.it_cosmetic
        )

        adorned_cosmetics = []
        adorned_ids = []

        adorned_styles = []

        stats_breakdown = {}

        space_adorned = 0

        for cosmetic in cosmetic_items:
            c = EwItem(id_item=cosmetic.get('id_item'))

            if c.item_props['adorned'] == 'true':

                hue = hue_static.hue_map.get(c.item_props.get('hue'))

                adorned_styles.append(c.item_props.get('fashion_style'))

                if c.item_props['id_cosmetic'] not in adorned_ids:
                    if any(stat in c.item_props.keys() for stat in ewcfg.playerstats_list):
                        for stat in ewcfg.playerstats_list:
                            if abs(int(c.item_props[stat])) > 0:
                                stats_breakdown[stat] = stats_breakdown.get(stat, 0) + int(c.item_props[stat])

                space_adorned += int(c.item_props['size'])

                adorned_ids.append(c.item_props['id_cosmetic'])
                adorned_cosmetics.append((hue.str_name + " " if hue != None else "") + cosmetic.get('name'))

        # show all the cosmetics that you have adorned.
        if len(adorned_cosmetics) > 0:
            response = "You whip out your smartphone and reverse your camera around to thoroughly analyze yourself.\n\n"
            response += "You have a {} adorned. ".format(ewutils.formatNiceList(adorned_cosmetics, 'and'))

            # fashion outfit, freshness rating.
            if len(adorned_cosmetics) >= 2:
                response += "\n\n"

                outfit_map = itm_utils.get_outfit_info(id_user=cmd.message.author.id, id_server=cmd.guild.id)
                user_data.persist()

                if outfit_map is not None:
                    response += itm_utils.get_style_freshness_rating(user_data=user_data, dominant_style=outfit_map['dominant_style'])

            response += " Your total freshness rating is {}.\n\n".format(user_data.freshness)

            space_remaining = ewutils.max_adornspace_bylevel(user_data.slimelevel) - space_adorned

            if space_remaining == 0:
                response += "You don't have cosmetic space left."
            else:
                response += "You have about {amount} adornable space.\n".format(amount=space_remaining)

        else:
            response = "You aren't wearing anything!"

    else:
        member = cmd.mentions[0]
        user_data = EwUser(member=member, data_level=2)

        cosmetic_items = bknd_item.inventory(
            id_user=member.id,
            id_server=cmd.guild.id,
            item_type_filter=ewcfg.it_cosmetic
        )

        adorned_cosmetics = []
        adorned_ids = []

        adorned_styles = []

        stats_breakdown = {}

        space_adorned = 0

        for cosmetic in cosmetic_items:
            c = EwItem(id_item=cosmetic.get('id_item'))

            if c.item_props['adorned'] == 'true':

                hue = hue_static.hue_map.get(c.item_props.get('hue'))

                adorned_styles.append(c.item_props.get('fashion_style'))

                if c.item_props['id_cosmetic'] not in adorned_ids:
                    if any(stat in c.item_props.keys() for stat in ewcfg.playerstats_list):
                        for stat in ewcfg.playerstats_list:
                            if abs(int(c.item_props[stat])) > 0:
                                stats_breakdown[stat] = stats_breakdown.get(stat, 0) + int(c.item_props[stat])

                space_adorned += int(c.item_props['size'])

                adorned_ids.append(c.item_props['id_cosmetic'])
                adorned_cosmetics.append((hue.str_name + " " if hue != None else "") + cosmetic.get('name'))

        # show all the cosmetics that you have adorned.
        if len(adorned_cosmetics) > 0:
            response = "You take out your smartphone and tab back over to {}'s Instagrime account to obsessively analyze their latest outfit with a mixture of unearned superiority and unbridled jealousy.\n\n".format(member.display_name)
            response += "They have a {} adorned. ".format(ewutils.formatNiceList(adorned_cosmetics, 'and'))

            # fashion outfit, freshness rating.
            if len(adorned_cosmetics) >= 2:
                response += "\n\n"

                if user_data.freshness < ewcfg.freshnesslevel_1:
                    response += "Their outfit is starting to look pretty fresh, but They’ve got a long way to go if they wanna be NLACakaNM’s next top model."
                elif user_data.freshness < ewcfg.freshnesslevel_2:
                    response += "Their outfit is low-key on point, not gonna lie. They’re goin’ places, kid."
                elif user_data.freshness < ewcfg.freshnesslevel_3:
                    response += "Their outfit is lookin’ fresh as hell, goddamn! They shop so much they can probably speak Italian."
                elif user_data.freshness < ewcfg.freshnesslevel_4:
                    response += "Their outfit is straight up **GOALS!** Like, honestly. I’m being, like, totally sincere right now. Their Instragrime has attracted a small following."
                else:
                    response += "Holy shit! Their outfit is downright, positively, without a doubt, 100% **ON FLEEK!!** They’ve blown up on Instragrime, and they’ve got modeling gigs with fashion labels all across the city."

            response += " Their total freshness rating is {}.\n\n".format(user_data.freshness)

            # gameplay relvant stuff, inspect order

            response += "All told, their outfit "

            stat_responses = []

            for stat in ewcfg.playerstats_list:

                if stat in stats_breakdown.keys():
                    if abs(int(stats_breakdown[stat])) > 0:

                        if int(stats_breakdown[stat]) > 0:
                            stat_response = "increases their "
                        else:
                            stat_response = "decreases their "

                        stat_response += "{stat} by {amount}".format(stat=stat, amount=int(stats_breakdown[stat]))

                        stat_responses.append(stat_response)

            if len(stat_responses) == 0:
                response += "doesn't affect their stats at all."
            else:
                response += ewutils.formatNiceList(names=stat_responses, conjunction="and") + ". \n\n"

            space_remaining = ewutils.max_adornspace_bylevel(user_data.slimelevel) - space_adorned

            if space_remaining == 0:
                response += "They don't have cosmetic space left."
            else:
                response += "They have about {amount} adornable space.\n".format(amount=space_remaining)

        else:
            response = "...But they aren't wearing anything!"

    return await fe_utils.send_response(response, cmd)


"""recycle your trash at the SlimeCorp Recycling plant"""


async def recycle(cmd):
    user_data = EwUser(member=cmd.message.author)
    if user_data.life_state == ewcfg.life_state_shambler:
        response = "You lack the higher brain functions required to {}.".format(cmd.tokens[0])
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    response = ""

    if user_data.poi != ewcfg.poi_id_recyclingplant:
        response = "You can only {} your trash at the Recycling Plant in Smogsburg.".format(cmd.tokens[0])
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    poi = poi_static.id_to_poi.get(user_data.poi)
    district_data = EwDistrict(district=poi.id_poi, id_server=user_data.id_server)

    if district_data.is_degraded():
        response = "{} has been degraded by shamblers. You can't {} here anymore.".format(poi.str_name, cmd.tokens[0])
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
    item_search = ewutils.flattenTokenListToString(cmd.tokens[1:])

    item_sought = bknd_item.find_item(item_search=item_search, id_user=cmd.message.author.id, id_server=cmd.guild.id if cmd.guild is not None else None)

    if item_sought:
        item = EwItem(id_item=item_sought.get("id_item"))

        if not item.soulbound:
            if item.item_type == ewcfg.it_weapon and user_data.weapon >= 0 and item.id_item == user_data.weapon:
                if user_data.weaponmarried:
                    weapon = static_weapons.weapon_map.get(item.item_props.get("weapon_type"))
                    response = "Woah, wow, hold on there! Domestic violence is one thing, but how could you just throw your faithful {} into a glorified incinerator? Look, we all have bad days, but that's no way to treat a weapon. At least get a proper divorce first, you animal.".format(weapon.str_weapon)
                    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                else:
                    user_data.weapon = -1
                    user_data.persist()
            elif item.item_type == ewcfg.it_weapon and user_data.sidearm >= 0 and item.id_item == user_data.sidearm:
                user_data.sidearm = -1
                user_data.persist()

            bknd_item.item_delete(id_item=item.id_item)

            pay = int(random.random() * 10 ** random.randrange(2, 6))
            response = "You put your {} into the designated opening. **CRUSH! Splat!** *hiss...* and it's gone. \"Thanks for keeping the city clean.\" a robotic voice informs you.".format(item_sought.get("name"))
            if item.item_props.get('id_furniture') == 'sord':
                response = "You jam the jpeg artifact into the recycling bin. It churns and sputters, desperately trying to turn it into anything of value. Needless to say, it fails. \"get a load of this hornses ass.\" a robotic voice informs you"

                if user_data.slimecoin >= 1:
                    response += ", nabbing 1 SlimeCoin from you out of spite."
                    user_data.change_slimecoin(n=-1, coinsource=ewcfg.coinsource_recycle)
                    user_data.persist()
                else:
                    response += "."
            elif pay == 0:
                item_reward = random.choice(vendors.mine_results)

                item_props = itm_utils.gen_item_props(item_reward)

                bknd_item.item_create(
                    item_type=item_reward.item_type,
                    id_user=cmd.message.author.id,
                    id_server=cmd.guild.id,
                    item_props=item_props
                )

                ewstats.change_stat(user=user_data, metric=ewcfg.stat_lifetime_poudrins, n=1)

                response += "\n\nYou receive a {}!".format(item_reward.str_name)
            else:
                user_data.change_slimecoin(n=pay, coinsource=ewcfg.coinsource_recycle)
                user_data.persist()

                response += "\n\nYou receive {:,} SlimeCoin.".format(pay)

        else:
            response = "You can't {} soulbound items.".format(cmd.tokens[0])
    else:
        if item_search:
            response = "You don't have one"
        else:
            response = "{} which item? (check **!inventory**)".format(cmd.tokens[0])

    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


"""
	advertise help services
"""


async def help(cmd):
    response = ""
    topic = None
    user_data = EwUser(member=cmd.message.author)
    resp_cont = EwResponseContainer(id_server=cmd.guild.id)

    # help only checks for districts while in game channels

    # checks if user is in a college or if they have a game guide
    gameguide = bknd_item.find_item(item_search="gameguide", id_user=cmd.message.author.id, id_server=cmd.guild.id if cmd.guild is not None else None, item_type_filter=ewcfg.it_item)

    if user_data.poi == ewcfg.poi_id_neomilwaukeestate or user_data.poi == ewcfg.poi_id_nlacu or gameguide:
        if not len(cmd.tokens) > 1:
            topic_counter = 0
            topic_total = 0
            weapon_topic_counter = 0
            weapon_topic_total = 0

            # list off help topics to player at college
            response = "(Use !help [topic] to learn about a topic. Example: '!help gangs')\n\nWhat would you like to learn about? Topics include: \n"

            # display the list of topics in order
            topics = ewcfg.help_responses_ordered_keys
            for topic in topics:
                topic_counter += 1
                topic_total += 1
                response += "**{}**".format(topic)
                if topic_total != len(topics):
                    response += ", "

                if topic_counter == 5:
                    topic_counter = 0
                    response += "\n"

            response += '\n\n'

            weapon_topics = ewcfg.weapon_help_responses_ordered_keys
            for weapon_topic in weapon_topics:
                weapon_topic_counter += 1
                weapon_topic_total += 1
                response += "**{}**".format(weapon_topic)
                if weapon_topic_total != len(weapon_topics):
                    response += ", "

                if weapon_topic_counter == 5:
                    weapon_topic_counter = 0
                    response += "\n"

            resp_cont.add_channel_response(cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

        else:
            topic = ewutils.flattenTokenListToString(cmd.tokens[1:])
            if topic in ewcfg.help_responses:
                response = ewcfg.help_responses[topic]
                resp_cont.add_channel_response(cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                if topic == 'mymutations':
                    mutations = user_data.get_mutations()
                    if len(mutations) == 0:
                        response = "\nWait... you don't have any!"
                        resp_cont.add_channel_response(cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                    else:
                        for mutation in mutations:
                            response = "**{}**: {}".format(mutation, ewcfg.mutation_descriptions[mutation])
                            resp_cont.add_channel_response(cmd.message.channel, response)

            else:
                response = 'ENDLESS WAR questions your belief in the existence of such a topic. Try referring to the topics list again by using just !help.'
                resp_cont.add_channel_response(cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
    else:
        # user not in college, check what help message would apply to the subzone they are in

        # poi variable assignment used for checking if player is in a vendor subzone or not
        # poi = ewmap.fetch_poi_if_coordless(cmd.message.channel.name)

        poi = poi_static.id_to_poi.get(user_data.poi)

        dojo_topics = [
            "dojo", "sparring", "combat", ewcfg.weapon_id_revolver,
            ewcfg.weapon_id_dualpistols, ewcfg.weapon_id_shotgun, ewcfg.weapon_id_rifle,
            ewcfg.weapon_id_smg, ewcfg.weapon_id_minigun, ewcfg.weapon_id_bat, ewcfg.weapon_id_brassknuckles,
            ewcfg.weapon_id_katana, ewcfg.weapon_id_broadsword, ewcfg.weapon_id_nunchucks,
            ewcfg.weapon_id_scythe, ewcfg.weapon_id_yoyo, ewcfg.weapon_id_bass,
            ewcfg.weapon_id_umbrella, ewcfg.weapon_id_knives, ewcfg.weapon_id_molotov,
            ewcfg.weapon_id_grenades, ewcfg.weapon_id_garrote,
            "normal", "multiple-hit", "variable-damage",
            "small-game", "heavy", "defensive",
            "precision", "incendiary", "explosive",
        ]

        if poi is None:
            # catch-all response for when user isn't in a sub-zone with a help response
            response = ewcfg.generic_help_response

        elif cmd.message.channel.name in [ewcfg.channel_mines, ewcfg.channel_cv_mines, ewcfg.channel_tt_mines]:
            # mine help
            response = ewcfg.help_responses['mining']
        elif (len(poi.vendors) >= 1) and not cmd.message.channel.name in [ewcfg.channel_dojo, ewcfg.channel_greencakecafe, ewcfg.channel_glocksburycomics]:
            # food help
            response = ewcfg.help_responses['food']
        elif cmd.message.channel.name in [ewcfg.channel_greencakecafe, ewcfg.channel_glocksburycomics]:
            # zines help
            response = ewcfg.help_responses['zines']
        elif cmd.message.channel.name in ewcfg.channel_dojo and not len(cmd.tokens) > 1:
            # dojo help
            response = "For general dojo information, do **'!help dojo'**. For information about the sparring and weapon rank systems, do **'!help sparring.'**. For general information about combat, do **'!help combat'**. For information about a specific weapon, do **'!help [weapon/weapon type]'**. The different weapon types are: **normal**, **multiple-hit**, **variable-damage**, **small-game**, **heavy**, **defensive**, **precision**, **incendiary**, and **explosive**."  # For information about the sap system, do **'!help sap'**.
        elif cmd.message.channel.name in ewcfg.channel_dojo and len(cmd.tokens) > 1:
            topic = ewutils.flattenTokenListToString(cmd.tokens[1:])
            if topic in dojo_topics and topic in ewcfg.help_responses:
                response = ewcfg.help_responses[topic]
            else:
                response = 'ENDLESS WAR questions your belief in the existence of such information regarding the dojo. Try referring to the topics list again by using just !help.'
        elif cmd.message.channel.name in [ewcfg.channel_jr_farms, ewcfg.channel_og_farms, ewcfg.channel_ab_farms]:
            # farming help
            response = ewcfg.help_responses['farming']
        elif cmd.message.channel.name in ewcfg.channel_slimeoidlab and not len(cmd.tokens) > 1:
            # labs help
            response = "For information on slimeoids, do **'!help slimeoids'**. To learn about your current mutations, do **'!help mymutations'**"
        elif cmd.message.channel.name in ewcfg.channel_slimeoidlab and len(cmd.tokens) > 1:
            topic = ewutils.flattenTokenListToString(cmd.tokens[1:])
            if topic == 'slimeoids':
                response = ewcfg.help_responses['slimeoids']
            elif topic == 'mymutations':
                response = ewcfg.help_responses['mymutations']
                mutations = user_data.get_mutations()
                if len(mutations) == 0:
                    response += "\nWait... you don't have any!"
                else:
                    for mutation in mutations:
                        response += "\n**{}**: {}".format(mutation, ewcfg.mutation_descriptions[mutation])
            else:
                response = 'ENDLESS WAR questions your belief in the existence of such information regarding the laboratory. Try referring to the topics list again by using just !help.'
        elif cmd.message.channel.name in poi_static.transport_stops_ch:
            # transportation help
            response = ewcfg.help_responses['transportation']
        elif cmd.message.channel.name in ewcfg.channel_stockexchange:
            # stock exchange help
            response = ewcfg.help_responses['stocks']
        elif cmd.message.channel.name in ewcfg.channel_casino:
            # casino help
            response = ewcfg.help_responses['casino']
        elif cmd.message.channel.name in ewcfg.channel_sewers:
            # death help
            response = ewcfg.help_responses['death']

        elif cmd.message.channel.name in ewcfg.channel_realestateagency:
            # real estate help
            response = ewcfg.help_responses['realestate']
        elif cmd.message.channel.name in [
            ewcfg.channel_tt_pier,
            ewcfg.channel_afb_pier,
            ewcfg.channel_jr_pier,
            ewcfg.channel_cl_pier,
            ewcfg.channel_se_pier,
            ewcfg.channel_jp_pier,
            ewcfg.channel_ferry
        ]:
            # fishing help
            response = ewcfg.help_responses['fishing']
        elif user_data.poi in poi_static.outskirts:
            # hunting help
            response = ewcfg.help_responses['hunting']
        elif poi_static.id_to_poi.get(user_data.poi).is_apartment:
            response = "This is your apartment, your home away from home. You can store items here, but if you can't pay rent they will be ejected to the curb. You can store slimeoids here, too, but eviction sends them back to the real estate agency. You can only access them once you rent another apartment. Rent is charged every two IRL days, and if you can't afford the charge, you are evicted. \n\nHere's a command list. \n!depart: Leave your apartment. !goto commands work also.\n!look: look at your apartment, including all its items.\n!inspect <item>: Examine an item in the room or in your inventory.\n!stow <item>: Place an item in the room.\n!fridge/!closet/!decorate <item>: Place an item in a specific spot.\n!snag <item>: Take an item from storage.\n!unfridge/!uncloset/!undecorate <item>: Take an item from a specific spot.\n!freeze/!unfreeze <slimeoid name>: Deposit and withdraw your slimeoids. You can have 3 created at a time.\n!aptname <new name>:Change the apartment's name.\n!aptdesc <new name>: Change the apartment's base description.\n!bootall: Kick out any unwanted visitors in your apartment.\n!shelve <zine>:Store zines on your bookshelf.\n!unshelve <zine>: Take zines out of your bookshelf"
        else:
            # catch-all response for when user isn't in a sub-zone with a help response
            response = ewcfg.generic_help_response

        resp_cont.add_channel_response(cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    # Send the response to the player.
    await resp_cont.post()


# await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def commands(cmd):
    user_data = EwUser(member=cmd.message.author)
    response = ""
    category = ewutils.flattenTokenListToString(tokens=cmd.tokens[1:])

    if cmd.tokens_count == 1:
        response += location_commands(cmd)
        response += mutation_commands(cmd)
        response += item_commands(cmd)
        if response != "":
            response += "\n\nLook up basic commands with !commands basic, \nor a full list with !commands categories."
            return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if "categories" in category:
        response += "Categories are: \nbasic: basic info.\nmyitems: Commands for items you have.\nmylocation: Commands based in this area.\nmymutations: Commands for the mutations you currently have.\nmyfaction: Commands for the faction you're in.\nmyrace: The command for your current race.\ncombat: Combat-based commands.\ncapping: Capping-based commands.\nplayerinfo: Commands that tell you some of your statistics.\noutsidelinks: These display links to outside the server.\nitems: Show item-related commands.\ncosmeticsanddyes: Display information on cosmetics and dyes.\nsmelting: Smelting related commands.\ntrading: Trading related commands.\nquadrants: Quadrant related commands.\nslimeoids: Slimeoid-related commands.\njuvies: Commands for juvies.\nenlisted: Commands for enlisted players.\ncorpses:Commands for corpses.\nmisc: Miscellaneous commands.\nflavor: Other shitposty type commands.\nallitem: All item-specific commands.\nallmutation: All mutation specific commands.\nYou can also check the commands of a specific location using !commands location <district>."

    if cmd.tokens_count == 1 or "basic" in category:
        response += "\n\n" + ewcfg.basic_commands

    if ewutils.flattenTokenListToString(tokens=cmd.tokens[1]) == 'location':
        poi_look = ewutils.flattenTokenListToString(tokens=cmd.tokens[2])
        poi_sought = poi_static.id_to_poi.get(poi_look)
        if poi_sought:
            command_output = location_commands(cmd=cmd, search_poi=poi_sought.id_poi)
            if command_output != "":
                response += command_output
            else:
                response = "No commands for that region."
        else:
            response = "Not a real place."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if "myitems" in category:
        response += "\n\n" + item_commands(cmd)
    if "mylocation" in category:
        response += "\n\n" + location_commands(cmd)
    if "mymutations" in category:
        response += "\n\n" + mutation_commands(cmd)
    if "myfaction" in category:
        if user_data.life_state == ewcfg.life_state_juvenile:
            response += "\n\n" + ewcfg.juvenile_commands
        elif user_data.life_state == ewcfg.life_state_corpse:
            response += "\n\n" + ewcfg.corpse_commands
        else:
            if user_data.faction == 'rowdys':
                response += "\n\n" + "!thrash: Thrashing is a rowdy's fucking lifeblood.\n"
            elif user_data.faction == 'killers':
                response += "\n\n" + "!dab: To dab on some haters.\n"
            response += ewcfg.enlisted_commands
    if "juvies" in category:
        response += "\n\n" + ewcfg.juvenile_commands
    if "corpses" in category:
        response += "\n\n" + ewcfg.corpse_commands
    if "enlisted" in category:
        response += "\n\n" + ewcfg.enlisted_commands
    if "myrace" in category:
        race = user_data.race
        if ewcfg.race_unique_commands.get(race) is not None:
            response += "\n\n" + ewcfg.race_unique_commands.get(race)
        else:
            response += "\n\nNo racial commands found."
    if "combat" in category:
        response += "\n\n" + ewcfg.combat_commands
    if "capping" in category:
        response += "\n\n" + ewcfg.capping_commands
    if "playerinfo" in category:
        response += "\n\n" + ewcfg.player_info_commands
    if "outsidelinks" in category:
        response += "\n\n" + ewcfg.external_link_commands
    if "items" in category:
        response += "\n\n" + ewcfg.item_commands
    if "cosmeticsanddyes" in category:
        response += "\n\n" + ewcfg.cosmetics_dyes_commands
    if "smelting" in category:
        response += "\n\n" + ewcfg.smelting_commands
    if "trading" in category:
        response += "\n\n" + ewcfg.trading_commands
    if "quadrants" in category:
        response += "\n\n" + ewcfg.quadrant_commands
    if "misc" in category:
        response += "\n\n" + ewcfg.miscellaneous_commands
    if "flavor" in category:
        response += "\n\n" + ewcfg.flavor_commands
    if "allitem" in category:
        response += "\n\n"
        for item in ewcfg.item_unique_commands.keys():
            response += "\n" + ewcfg.item_unique_commands.get(item)
    if "allmutation" in category:
        response += "\n\n"
        for item in ewcfg.mutation_unique_commands.keys():
            response += "\n" + ewcfg.mutation_unique_commands.get(item)
    if response == "" or '!' not in response:
        response = "No commands found."

    messageArray = ewutils.messagesplit(stringIn=response)

    for message in messageArray:
        await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, message))


# return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

""" pure flavor command, howls """


async def cmd_howl(cmd):
    user_data = EwUser(member=cmd.message.author)
    slimeoid = EwSlimeoid(member=cmd.message.author)
    response = ewcfg.howls[random.randrange(len(ewcfg.howls))]

    if (slimeoid.life_state == ewcfg.slimeoid_state_active) and (user_data.life_state != ewcfg.life_state_corpse):
        response += "\n{} howls along with you! {}".format(str(slimeoid.name), ewcfg.howls[random.randrange(len(ewcfg.howls))])

    await fe_utils.send_response(response, cmd)


async def cmd_moan(cmd):
    user_data = EwUser(member=cmd.message.author)
    slimeoid = EwSlimeoid(member=cmd.message.author)
    response = ewcfg.moans[random.randrange(len(ewcfg.moans))]

    if user_data.life_state != ewcfg.life_state_shambler and user_data.race != ewcfg.race_shambler:
        response = "You're not really feeling it... Maybe if you lacked cognitive function, you'd be more inclined to moan, about brains, perhaps."
        return await fe_utils.send_response(response, cmd)

    if (slimeoid.life_state == ewcfg.slimeoid_state_active):
        response += "\n{} moans along with you! {}".format(str(slimeoid.name), ewcfg.moans[random.randrange(len(ewcfg.moans))])

    await fe_utils.send_response(response, cmd)


"""
	Harvest is not and has never been a command.
	(Krak made it a command once you fool)
"""


async def harvest(cmd):
    response = '**HARVEST IS NOT A COMMAND YOU FUCKING IDIOT**'
    await fe_utils.send_response(response, cmd)


"""
	Salute the NLACakaNM flag.
"""


async def salute(cmd):
    response = 'https://ew.krakissi.net/img/nlacakanm_flag.gif'
    await fe_utils.send_response(response, cmd)


"""
	Burn the NLACakaNM flag.
"""


async def unsalute(cmd):
    response = 'https://ew.krakissi.net/img/nlacakanm_flag_burning.gif'
    await fe_utils.send_response(response, cmd)


"""
	TFAAAP HURL GIF
"""


async def hurl(cmd):
    response = 'https://ew.krakissi.net/img/tfaaap-hurl.gif'
    await fe_utils.send_response(response, cmd)


"""
	advertise patch notes
"""


async def patchnotes(cmd):
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, 'Look for the latest patchnotes on the news page: https://ew.krakissi.net/news/'))


"""
	Link to the RFCK wiki.
"""


async def wiki(cmd):
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, 'Rowdy Fuckers Cop Killers Wiki: https://rfck.miraheze.org/wiki/Main_Page'))


"""
	Link to the fan art booru.
"""


async def booru(cmd):
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, 'Rowdy Fuckers Cop Killers Booru: http://rfck.booru.org/'))


"""
	Link to the RFCK bandcamp.
"""


async def bandcamp(cmd):
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, 'Rowdy Fuckers Cop Killers Bandcamp: https://rowdyfuckerscopkillers.bandcamp.com/releases'))


"""
	Link to the Gameplay category in the RFCK wiki
"""


async def tutorial(cmd):
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, 'In-depth tutorial of all the gameplay mechanics in the Endless War: https://rfck.miraheze.org/wiki/Category:Gameplay'))


"""
	Link to the leaderboards on ew.krakissi.net.
"""


async def leaderboard(cmd):
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, 'Live leaderboards: https://ew.krakissi.net/stats/'))


async def lol(cmd):
    response = 'You laugh out loud!'
    await fe_utils.send_response(response, cmd)


async def paycheck(cmd):
    user_data = EwUser(member=cmd.message.author)
    credits = user_data.salary_credits

    if credits == 0:
        response = "You don't have any salary credits..."
    else:
        response = "You have {:,} salary credits.".format(credits)

        if credits > 10000:
            response += " They can be exchanged for {:,} slime with !payday at SlimeCorp HQ.".format(int(credits / 10000))

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def payday(cmd):
    user_data = EwUser(member=cmd.message.author)
    credits = user_data.salary_credits

    market_data = EwMarket(id_server=cmd.message.author.guild.id)

    if user_data.poi != ewcfg.poi_id_slimecorphq:
        response = "You don't work here."
    elif user_data.faction != ewcfg.faction_slimecorp:
        response = "You don't work here."
    elif market_data.clock < 6 or market_data.clock >= 8:
        response = "The kind lady at the receptionist desk informs you that paychecks can only be collected between 6 and 8 AM."
    elif credits <= 9999:
        response = "You don't have any salary credits that can be exchanged..."
    else:
        user_data.salary_credits = 0

        slime_added = int(credits / 10000)
        user_data.change_slimes(n=slime_added, source=ewcfg.coinsource_salary)

        user_data.persist()

        response = "You cash in all of your salary credits for {:,} slime.".format(slime_added)

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def pray(cmd):
    user_data = EwUser(member=cmd.message.author)
    if user_data.life_state == ewcfg.life_state_shambler:
        response = "You lack the higher brain functions required to {}.".format(cmd.tokens[0])
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if cmd.message.channel.name != ewcfg.channel_endlesswar:
        response = "You must be in the presence of your lord if you wish to pray to him."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    poi = poi_static.id_to_poi.get(user_data.poi)
    district_data = EwDistrict(district=poi.id_poi, id_server=user_data.id_server)

    if district_data.is_degraded():
        response = "{} has been degraded by shamblers. You can't {} here anymore.".format(poi.str_name, cmd.tokens[0])
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if len(cmd.mention_ids) == 0:
        target_type = "ew"
    else:
        target_type = ewutils.mention_type(cmd, cmd.mention_ids[0])

    # endless war disapoves of praying to others and has a high chance to kill
    if target_type != "ew":
        probabilityofdeath = 20
        diceroll = random.randint(1, 100)

        # don't kill kingpins
        if user_data.life_state != ewcfg.life_state_kingpin and diceroll < probabilityofdeath:
            response = "ENDLESS WAR doesn’t respond. You squint, looking directly into his eye, and think you begin to see particle effects begin to accumulate..."
            await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
            await asyncio.sleep(3)

            user_data = EwUser(member=cmd.message.author)
            user_data.trauma = ewcfg.trauma_id_environment
            die_resp = user_data.die(cause=ewcfg.cause_praying)
            user_data.persist()
            await ewrolemgr.updateRoles(client=cmd.client, member=cmd.message.author)
            await die_resp.post()

            response = "ENDLESS WAR completely and utterly obliterates you with a bone-hurting beam."
        else:
            response = "ENDLESS WAR disapproves of this idolatry."


    else:
        if user_data.life_state == ewcfg.life_state_kingpin:
            # slimernalia 2019 revieal (this was left in for a long time lmao)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"https://i.imgur.com/WgnoDSA.gif"
            #	))
            #	await asyncio.sleep(9)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"https://i.imgur.com/M5GWGGc.gif"
            #	))
            #	await asyncio.sleep(3)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"https://i.imgur.com/fkLZ3XX.gif"
            #	))
            #	await asyncio.sleep(3)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"https://i.imgur.com/lUajXCs.gif"
            #	))
            #	await asyncio.sleep(9)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"https://i.imgur.com/FIuGl0C.png"
            #	))
            #	await asyncio.sleep(6)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"BUT SERIOUSLY, FOLKS... https://i.imgur.com/sAa0uwB.png"
            #	))
            #	await asyncio.sleep(3)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"IT'S SLIMERNALIA! https://i.imgur.com/lbLNJNC.gif"
            #	))
            #	await asyncio.sleep(6)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"***WHRRRRRRRRRRRR*** https://i.imgur.com/pvCfBQ2.gif"
            #	))
            #	await asyncio.sleep(6)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"***WHRRRRRRRRRRRR*** https://i.imgur.com/e2PY1VJ.gif"
            #	))
            #	await asyncio.sleep(3)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"DELICIOUS KINGPIN SLIME... https://i.imgur.com/2Cp1u43.png"
            #	))
            #	await asyncio.sleep(3)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(
            #		cmd.message.author,
            #		"JUST ENOUGH FOR A WEEK OR TWO OF CLEAR SKIES... https://i.imgur.com/L7T3V5b.gif"
            #	))
            #	await asyncio.sleep(9)
            #	await fe_utils.send_message(cmd.client, cmd.message.channel,
            #		"@everyone Yo, Slimernalia! https://imgur.com/16mzAJT"
            #	)
            #	response = "NOW GO FORTH AND SPLATTER SLIME."
            #	market_data = EwMarket(id_server = cmd.guild.id)
            #	market_data.weather = ewcfg.weather_sunny
            #	market_data.persist()

            # kingpins don't die or get poudrins
            responses_list = ewcfg.pray_responses_list

            if user_data.slimes > 1000000:
                responses_list = responses_list + ["ENDLESS WAR is impressed by your vast amounts of slime."]
            else:
                responses_list = responses_list + ["ENDLESS WAR can’t help but laugh at how little slime you have."]

            response = random.choice(responses_list)
        else:
            # Generates a random integer from 1 to 100. If it is below the prob of poudrin, the player gets a poudrin.
            # If the random integer is above prob of poudrin but below probofpoud+probofdeath, then the player dies. Else,
            # the player is blessed with a response from EW.
            probabilityofpoudrin = 10
            probabilityofdeath = 10
            diceroll = random.randint(1, 100)

            # Redeem the player for their sins.
            market_data = EwMarket(id_server=cmd.guild.id)
            market_data.global_swear_jar = max(0, market_data.global_swear_jar - 3)
            market_data.persist()
            user_data.persist()

            if diceroll < probabilityofpoudrin:  # Player gets a poudrin.
                item = random.choice(vendors.mine_results)

                item_props = itm_utils.gen_item_props(item)

                bknd_item.item_create(
                    item_type=item.item_type,
                    id_user=cmd.message.author.id,
                    id_server=cmd.guild.id,
                    item_props=item_props
                )

                response = "ENDLESS WAR takes pity on you, and with a minor tremor he materializes a {} in your pocket.".format(item.str_name)

            elif diceroll < (probabilityofpoudrin + probabilityofdeath):  # Player gets a face full of bone-hurting beam.
                response = "ENDLESS WAR doesn’t respond. You squint, looking directly into his eye, and think you begin to see particle effects begin to accumulate..."
                await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                await asyncio.sleep(3)

                user_data = EwUser(member=cmd.message.author)
                user_data.trauma = ewcfg.trauma_id_environment
                die_resp = user_data.die(cause=ewcfg.cause_praying)
                user_data.persist()
                await ewrolemgr.updateRoles(client=cmd.client, member=cmd.message.author)
                await die_resp.post()

                response = "ENDLESS WAR completely and utterly obliterates you with a bone-hurting beam."

            else:
                responses_list = ewcfg.pray_responses_list

                if user_data.slimes > 1000000:
                    responses_list = responses_list + ["ENDLESS WAR is impressed by your vast amounts of slime."]
                else:
                    responses_list = responses_list + ["ENDLESS WAR can’t help but laugh at how little slime you have."]

                response = random.choice(responses_list)

    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def check_mastery(cmd):
    user_data = EwUser(member=cmd.message.author)
    if user_data.weapon != -1:
        weapon_item = EwItem(user_data.weapon)
        equipped_type = weapon_item.item_props.get("weapon_type")
    else:
        equipped_type = "unarmed"

    message = "\nYou close your eyes for a moment, recalling your masteries: \n"
    if cmd.mentions_count > 0:
        response = "You can only recall your own weapon masteries!"
    else:
        wepskills = ewutils.weaponskills_get(member=cmd.message.author)
        for skill in wepskills:
            # Now actually grabs the mastery string! Rejoice!
            # In case someone somehow got a fucked up weapon, just skip it and don't think about it
            if static_weapons.weapon_map.get(skill) is None:
                continue
            master_weapon_response = (static_weapons.weapon_map[skill]).str_weaponmaster_self + '\n'
            if master_weapon_response == "\n":
                continue
            # Prints masteries above the mastery threshold as "master" skills, whereas those below are "rookie" skills
            if wepskills[skill] >= 5:
                message += master_weapon_response.format(rank=wepskills[skill] - 4, title="master")
            if wepskills[skill] < 5 and (wepskills[skill] > 0 or skill == equipped_type):
                message += master_weapon_response.format(rank=wepskills[skill], title="rookie")
        response = message

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def get_attire(cmd):
    user_data = EwUser(member=cmd.message.author)
    status = user_data.getStatusEffects()
    if user_data.poi != ewcfg.poi_id_thebreakroom:
        response = "Are you a Slimecorp Security Force official, planted firmly in their lavish breakroom? No? Then you're not getting shit."
    elif ewcfg.status_kevlarattire_id in status:
        response = "You're already armed, though. This stuff's too expensive so the company's not gonna let you double dip."
    elif user_data.life_state != ewcfg.life_state_enlisted:
        response = "You're not committed enough to wear this attire. You're a slob. How did you even get in here?"
    else:
        response = "You suit up in top-of-the-line Kevlar attire. Sleek. Professional. Bulletproof."
        await assign_status_effect(status_name='kevlarattire', user_id=cmd.message.author.id, server_id=cmd.guild.id, cmd=cmd)
    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


"""
    SLIMERNALIA COMMANDS
"""


# Show a player's festivity
async def festivity(cmd):
    if cmd.mentions_count == 0:
        user_data = EwUser(member=cmd.message.author)
        response = "You currently have {:,} festivity.".format(user_data.get_festivity())

    else:
        member = cmd.mentions[0]
        user_data = EwUser(member=member)
        response = "{} currently has {:,} festivity.".format(member.display_name, user_data.get_festivity())

    # Send the response to the player.
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def wrap(cmd):
    if cmd.tokens_count != 4:
        response = 'To !wrap a gift, you need to specify a recipient, message, and item, like so:\n```!wrap @munchy#6443 "Sample text." chickenbucket```'
        return await fe_utils.send_message(cmd.client, cmd.message.channel, response)

    if cmd.mentions_count == 0:
        response = "Who exactly are you giving your gift to?"
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if cmd.mentions_count > 1:
        response = "Back it up man, the rules are one gift for one person!"
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    recipient = cmd.mentions[0]
    recipient_data = EwUser(member=recipient)

    member = cmd.message.author
    user_data = EwUser(member=cmd.message.author)

    if recipient_data.id_user == user_data.id_user:
        response = "C'mon man, you got friends, don't you? Try and give a gift to someone other than yourself."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    paper_sought = bknd_item.find_item(item_search="wrappingpaper", id_user=cmd.message.author.id, id_server=cmd.guild.id, item_type_filter=ewcfg.it_item)

    if paper_sought:
        paper_item = EwItem(id_item=paper_sought.get('id_item'))

    if paper_sought and paper_item.item_props.get('context') == ewcfg.context_wrappingpaper:
        paper_name = paper_sought.get('name')
    else:
        response = "How are you going to wrap a gift without any wrapping paper?"
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    gift_message = cmd.tokens[2]

    item_search = ewutils.flattenTokenListToString(cmd.tokens[3:])
    item_sought = bknd_item.find_item(item_search=item_search, id_user=cmd.message.author.id, id_server=cmd.guild.id)

    if item_sought:
        item = EwItem(id_item=item_sought.get('id_item'))
        if item.item_type == ewcfg.it_item:
            if item.item_props.get('id_item') == "gift":
                response = "It's already wrapped."
                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
        if item.soulbound:
            response = "It's a nice gesture, but trying to gift someone a Soulbound item is going a bit too far, don't you think?"
        elif bknd_item.check_inv_capacity(user_data=user_data, item_type=ewcfg.it_item):
            response = ewcfg.str_generic_inv_limit.format(ewcfg.it_item)
        else:
            gift_name = "Gift"

            gift_address = 'To {}, {}. From, {}'.format(recipient.display_name, gift_message, member.display_name, )

            gift_desc = "A gift wrapped in {}. Wonder what's inside?\nThe front of the tag reads '{}'\nOn the back of the tag, an ID number reads **({})**.".format(paper_name, gift_address, item.id_item)

            response = "You shroud your {} in {} and slap on a premade bow. Onto it, you attach a note containing the following text: '{}'.\nThis small act of kindness manages to endow you with Slimernalia spirit, if only a little.".format(item_sought.get('name'), paper_name, gift_address)

            bknd_item.item_create(
                id_user=cmd.message.author.id,
                id_server=cmd.guild.id,
                item_type=ewcfg.it_item,
                item_props={
                    'item_name': gift_name,
                    'id_item': "gift",
                    'item_desc': gift_desc,
                    'context': gift_address,
                    'acquisition': "{}".format(item_sought.get('id_item')),
                    # flag indicating if the gift has already been given once so as to not have people farming festivity through !giving
                    'gifted': "false"
                }
            )
            bknd_item.give_item(id_item=item_sought.get('id_item'), id_user=str(cmd.message.author.id) + "gift", id_server=cmd.guild.id)
            bknd_item.item_delete(id_item=paper_item.id_item)

            user_data.festivity += ewcfg.festivity_on_gift_wrapping

            user_data.persist()
    else:
        if item_search == "" or item_search == None:
            response = "Specify the item you want to wrap."
        else:
            response = "Are you sure you have that item?"
    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def yoslimernalia(cmd):
    await fe_utils.send_message(cmd.client, cmd.message.channel, '@everyone Yo, Slimernalia!', filter_everyone=False)


""" show player's slimecoin balance """


async def slimecoin(cmd):
    if cmd.mentions_count == 0:
        user_data = EwUser(member=cmd.message.author)
        coins = user_data.slimecoin
        credits = user_data.salary_credits
        response = "You have {:,} SlimeCoin".format(coins)

        if credits != 0:
            response += " and {:,} SlimeCorp Salary Credits.".format(credits)
        else:
            response += "."

    else:
        member = cmd.mentions[0]
        user_data = EwUser(member=member)
        coins = user_data.slimecoin
        credits = user_data.salary_credits
        response = "{} has {:,} SlimeCoin".format(member.display_name, coins)

        if credits != 0:
            response += " and {:,} SlimeCorp Salary Credits.".format(credits)
        else:
            response += "."

    # Send the response to the player.
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


""" show player's shares in a stock """


async def shares(cmd):
    user_data = EwUser(member=cmd.message.author)
    if user_data.life_state == ewcfg.life_state_shambler:
        response = "You lack the higher brain functions required to {}.".format(cmd.tokens[0])
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    stock = ""
    response = ""

    if cmd.tokens_count > 0:
        stock = ewutils.flattenTokenListToString(cmd.tokens[1:])

    if stock in ewcfg.stocks:
        response = get_user_shares_str(id_server=user_data.id_server, id_user=user_data.id_user, stock=stock)

    elif stock == "":
        for stock in ewcfg.stocks:
            response += "\n"
            response += get_user_shares_str(id_server=user_data.id_server, id_user=user_data.id_user, stock=stock)

    else:
        response = "That's not a valid stock name, please use a proper one, you cunt: {}".format(ewutils.formatNiceList(ewcfg.stocks))

    # Send the response to the player.
    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


"""
    SWILLDERMUK COMMANDS
"""


async def prank(cmd):
    # User must have the Janus Mask adorned, and must use the command in a capturable district's channel
    user_data = EwUser(member=cmd.message.author)

    if (ewutils.channel_name_is_poi(cmd.message.channel.name) == False):  # or (user_data.poi not in poi_static.capturable_districts):
        response = "The powers of the mask don't really resonate with you here."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    mentions_user = False
    use_mention_displayname = False
    if cmd.mentions_count > 0:
        mentions_user = True

    cosmetics = bknd_item.inventory(
        id_user=user_data.id_user,
        id_server=user_data.id_server,
        item_type_filter=ewcfg.it_cosmetic
    )
    adorned_cosmetics = []

    response = "You aren't funny enough to do that. Please be funnier."  # If it's not overwritten

    for cosmetic in cosmetics:
        cos = EwItem(id_item=cosmetic.get('id_item'))
        if cos.item_props['adorned'] == 'true':
            if cos.item_props['rarity'] == 'Swilldermuk':
                # print('success')

                item_action = ""
                use_mention_displayname = False
                reroll = True
                item = None

                while reroll:
                    rarity_roll = random.randrange(10)

                    if rarity_roll > 3:
                        prank_item = random.choice(static_items.prank_items_heinous)
                    elif rarity_roll > 0:
                        prank_item = random.choice(static_items.prank_items_scandalous)
                    else:
                        prank_item = random.choice(static_items.prank_items_forbidden)

                    item_props = itm_utils.gen_item_props(prank_item)

                    # Set the user ID to 0 so it can't be given, looted, etc, before it gets deleted.
                    prank_item_id = bknd_item.item_create(
                        item_type=prank_item.item_type,
                        id_user=0,
                        id_server=user_data.id_server,
                        item_props=item_props
                    )

                    item = EwItem(id_item=prank_item_id)

                    if (item.item_props['prank_type'] != ewcfg.prank_type_trap and mentions_user) or (item.item_props['prank_type'] == ewcfg.prank_type_trap and not mentions_user):
                        # Don't reroll the item choice.
                        reroll = False

                response = ''
                pluck_response = "With the power of the Janus Mask, {} plucks a prank item from the ether!\n".format(cmd.message.author.display_name)

                if item.item_props['prank_type'] == ewcfg.prank_type_instantuse:
                    item_action, response, use_mention_displayname, side_effect = await prank_utils.prank_item_effect_instantuse(cmd, item)
                    if side_effect != "":
                        response += await itm_utils.perform_prank_item_side_effect(side_effect, cmd=cmd)

                    response = pluck_response + response

                elif item.item_props['prank_type'] == ewcfg.prank_type_response:
                    item_action, response, use_mention_displayname, side_effect = await prank_utils.prank_item_effect_response(cmd, item)
                    if side_effect != "":
                        response += await itm_utils.perform_prank_item_side_effect(side_effect, cmd=cmd)

                    response = pluck_response + response

                elif item.item_props['prank_type'] == ewcfg.prank_type_trap:
                    item_action, response, use_mention_displayname, side_effect = await prank_utils.prank_item_effect_trap(cmd, item)

                    response = pluck_response + response

                if item_action == "delete":
                    bknd_item.item_delete(item.id_item)
                # prank_feed_channel = fe_utils.get_channel(cmd.guild, ewcfg.channel_prankfeed)
                # await fe_utils.send_message(cmd.client, prank_feed_channel, fe_utils.formatMessage((cmd.message.author if use_mention_displayname == False else cmd.mentions[0]), (response + "\n`-------------------------`")))

                elif item_action == "drop":
                    bknd_item.give_item(id_user=(user_data.poi + '_trap'), id_server=item.id_server, id_item=item.id_item)

                break

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage((cmd.message.author if use_mention_displayname == False else cmd.mentions[0]), response))


"""
    GVS COMMANDS
"""


async def gvs_print_grid(cmd):
    author = cmd.message.author
    user_data = EwUser(member=author)

    grid_map = hunt_utils.gvs_create_gaia_grid_mapping(user_data)

    debug = False
    if debug:
        blue_blank = ':blue_heart:'
        green_lawn = ':green_heart:'
        lime_lawn = ':yellow_heart:'
    else:
        blue_blank = ewcfg.emote_blankregional
        green_lawn = ewcfg.emote_greenlawn
        lime_lawn = ewcfg.emote_limelawn

    emote_set = []
    # print(grid_map)

    green_or_lime = lime_lawn
    for row in ewcfg.gvs_valid_coords_gaia:
        for coord in row:

            if green_or_lime == lime_lawn:
                green_or_lime = green_lawn
            else:
                green_or_lime = lime_lawn

            if coord in grid_map.keys():
                emote = ewcfg.gvs_enemy_emote_map[grid_map[coord]]

                if debug:
                    emote = ewcfg.gvs_enemy_emote_map_debug[grid_map[coord]]

                emote_set.append(emote)
            else:
                emote_set.append(green_or_lime)

    printed_grid_row_0 = "\n{}{}{}{}{}{}{}{}{}{}".format(
        blue_blank,
        ':one:',
        ':two:',
        ':three:',
        ':four:',
        ':five:',
        ':six:',
        ':seven:',
        ':eight:',
        ':nine:'
    )

    printed_grid_row_1 = "\n{}{}{}{}{}{}{}{}{}{}".format(
        ':regional_indicator_a:',
        emote_set[0],
        emote_set[1],
        emote_set[2],
        emote_set[3],
        emote_set[4],
        emote_set[5],
        emote_set[6],
        emote_set[7],
        emote_set[8],
    )

    printed_grid_row_2 = "\n{}{}{}{}{}{}{}{}{}{}".format(
        ':regional_indicator_b:',
        emote_set[9],
        emote_set[10],
        emote_set[11],
        emote_set[12],
        emote_set[13],
        emote_set[14],
        emote_set[15],
        emote_set[16],
        emote_set[17],
    )

    printed_grid_row_3 = "\n{}{}{}{}{}{}{}{}{}{}".format(
        ':regional_indicator_c:',
        emote_set[18],
        emote_set[19],
        emote_set[20],
        emote_set[21],
        emote_set[22],
        emote_set[23],
        emote_set[24],
        emote_set[25],
        emote_set[26],
    )

    printed_grid_row_4 = "\n{}{}{}{}{}{}{}{}{}{}".format(
        ':regional_indicator_d:',
        emote_set[27],
        emote_set[28],
        emote_set[29],
        emote_set[30],
        emote_set[31],
        emote_set[32],
        emote_set[33],
        emote_set[34],
        emote_set[35],
    )

    printed_grid_row_5 = "\n{}{}{}{}{}{}{}{}{}{}".format(
        ':regional_indicator_e:',
        emote_set[36],
        emote_set[37],
        emote_set[38],
        emote_set[39],
        emote_set[40],
        emote_set[41],
        emote_set[42],
        emote_set[43],
        emote_set[44],
    )

    full_grid_response = printed_grid_row_0 + printed_grid_row_1 + printed_grid_row_2 + printed_grid_row_3 + printed_grid_row_4 + printed_grid_row_5
    # print('Grid response length: {}'.format(len(full_grid_response)))

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, full_grid_response))


async def gvs_print_lane(cmd):
    author = cmd.message.author
    user_data = EwUser(member=author)

    debug = False

    response = ""
    if cmd.tokens_count != 2:
        response = "Which lane do you want to check? Options are A, B, C, D, or E"
    else:
        chosen_lane = cmd.tokens[1].lower()
        lanes = ['a', 'b', 'c', 'd', 'e']

        if chosen_lane not in lanes:
            response = "That's not a valid lane, bitch."
        else:

            lane_index = lanes.index(chosen_lane)
            row_used = ewcfg.gvs_valid_coords_gaia[lane_index]

            coord_sets = hunt_utils.gvs_create_gaia_lane_mapping(user_data, row_used)

            counter = 0
            for coord_set in coord_sets:
                current_coord = row_used[counter]
                counter += 1

                response += "\n**{}**: (".format(current_coord)
                if len(coord_set) == 0:
                    response += "Empty"
                else:
                    for enemy_id in coord_set:
                        if enemy_id == 'frozen':
                            response += "FROZEN"
                        else:
                            enemy_data = EwEnemy(id_server=user_data.id_server, id_enemy=enemy_id)
                            props = enemy_data.enemy_props

                            if debug:
                                response += ewcfg.gvs_enemy_emote_map_debug[enemy_data.enemytype]
                                if props.get('joybean') == 'true':
                                    response += "-{}".format(ewcfg.gvs_enemy_emote_map_debug[ewcfg.enemy_type_gaia_joybeans])
                                if props.get('metallicap') == 'true':
                                    response += "-{}".format(ewcfg.gvs_enemy_emote_map_debug[ewcfg.enemy_type_gaia_metallicaps])
                                elif props.get('aushuck') == 'true':
                                    response += "-{}".format(ewcfg.gvs_enemy_emote_map_debug[ewcfg.enemy_type_gaia_aushucks])
                            else:
                                response += ewcfg.gvs_enemy_emote_map[enemy_data.enemytype]
                                if props.get('joybean') == 'true':
                                    response += "-{}".format(ewcfg.gvs_enemy_emote_map[ewcfg.enemy_type_gaia_joybeans])
                                if props.get('metallicap') == 'true':
                                    response += "-{}".format(ewcfg.gvs_enemy_emote_map[ewcfg.enemy_type_gaia_metallicaps])
                                elif props.get('aushuck') == 'true':
                                    response += "-{}".format(ewcfg.gvs_enemy_emote_map[ewcfg.enemy_type_gaia_aushucks])

                            response += " "

                response += ") "

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def gvs_incubate_gaiaslimeoid(cmd):
    user_data = EwUser(member=cmd.message.author)
    valid_material = False

    if user_data.poi != ewcfg.poi_id_og_farms:
        response = "You lack the proper equipment to create a Gaiaslimeoid. Head to the Atomic Forest in Ooze Gardens Farms!"
    else:
        if cmd.tokens_count < 2:
            material_counter = 0
            material_total = 0
            response = "Please specify the crop material you will use. Options are...\n"
            for material in static_items.seedpacket_ingredient_list:
                material_counter += 1
                material_total += 1
                response += "**{}**".format(material)
                if material_total != len(static_items.seedpacket_ingredient_list):
                    response += ", "

                if material_counter == 5:
                    material_counter = 0
                    response += "\n"
        else:
            material = ewutils.flattenTokenListToString(cmd.tokens[1:])

            for material_id in static_items.seedpacket_ingredient_list:
                if material in material_id or material == material_id:
                    valid_material = True
                    break

            if not valid_material:
                response = "That's not a crop material you can use, bitch."
            else:

                material_item = bknd_item.find_item(item_search=material, id_user=cmd.message.author.id, id_server=cmd.message.guild.id if cmd.message.guild is not None else None, item_type_filter=ewcfg.it_item)
                if material_item == None:
                    response = "You don't have that crop material in your inventory, bitch."
                else:

                    generated_seedpacket_id = static_items.seedpacket_material_map[material_id]
                    item = static_items.item_map.get(generated_seedpacket_id)

                    item_type = ewcfg.it_item
                    if item != None:
                        bknd_item.item_delete(id_item=material_item.get('id_item'))
                        name = item.str_name

                        item_props = itm_utils.gen_item_props(item)

                        generated_item_id = bknd_item.item_create(
                            item_type=item_type,
                            id_user=cmd.message.author.id,
                            id_server=cmd.message.guild.id,
                            item_props=item_props
                        )

                        response = "You insert your crop material into the patent-pending Garden Ganker Homunculifier-9000:tm: and pull down hard on the large metallic lever. After a bunch of bells, whistles, and flashing lights sound off, out pops a {}!".format(name)

                    else:
                        return ewutils.logMsg("ERROR: Could not produce seed packet for material {}.".format(material))

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def gvs_fabricate_tombstone(cmd):
    user_data = EwUser(member=cmd.message.author)

    if user_data.poi != ewcfg.poi_id_nuclear_beach_edge:
        response = "You lack the proper equipment to fabricate a Tombstone. Head to Dr. Downpour's Laboratory at the edge of Nuclear Beach!"
    else:
        if cmd.tokens_count < 2:
            tombstone_counter = 0
            tombstone_total = 0
            enemy_counter = 0
            response = "Please specify the tombstone you want to fabricate. Options are...\n"
            for tombstone in static_items.tombstone_enemytype_map.keys():
                tombstone_counter += 1
                tombstone_total += 1
                response += "**{}**".format(tombstone)
                if tombstone_total != len(static_items.tombstone_enemytype_map):
                    response += ", "

                if enemy_counter == 5:
                    enemy_counter = 0
                    response += "\n"
        else:
            tombstone = ewutils.flattenTokenListToString(cmd.tokens[1:])
            if tombstone not in static_items.tombstone_enemytype_map.keys():
                response = "That's not a valid tombstone you can make, bitch."
            else:

                brainz = user_data.gvs_currency
                generated_tombstone_id = tombstone
                item = static_items.item_map.get(generated_tombstone_id)
                if item != None:
                    cost = item.cost
                    name = item.str_name
                    item_type = ewcfg.it_item

                    if cost > brainz:
                        response = "A {} costs {} brainz to fabricate, and you only have {}.".format(name, cost, brainz)
                    else:
                        user_data.gvs_currency -= cost

                        item_props = itm_utils.gen_item_props(item)

                        generated_item_id = bknd_item.item_create(
                            item_type=item_type,
                            id_user=cmd.message.author.id,
                            id_server=cmd.message.guild.id,
                            item_props=item_props
                        )

                        response = "You insert {} of your hard earned brainz into the state of the art Downpour 3D Bio-printer, watching carefully as the squishy pink organs are transformed into a {} before your very eyes! You take it out of the machine and go on your merry way.".format(cost, name)

                        user_data.persist()

                else:
                    return ewutils.logMsg("ERROR: Could not produce tombstone for tombstone ID {}.".format(generated_tombstone_id))

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def gvs_join_operation(cmd):
    seedpackets = static_items.seedpacket_ids
    tombstones = static_items.tombstone_ids
    time_now = int(time.time())

    user_data = EwUser(member=cmd.message.author)
    poi = poi_static.id_to_poi.get(user_data.poi)
    district_data = EwDistrict(district=user_data.poi, id_server=user_data.id_server)

    response = ""

    if ewutils.channel_name_is_poi(cmd.message.channel.name) == False:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You must {} in a zone's channel.".format(cmd.tokens[0])))

    if district_data.time_unlock > time_now:

        if int((district_data.time_unlock - time_now) / 60) <= 1:
            time_remaining = district_data.time_unlock - time_now
            time_used = 'seconds'
        else:
            time_remaining = int((district_data.time_unlock - time_now) / 60)
            time_used = 'minutes'

        response = "The area is too scarred from recent battles between the Garden Gankers and the Shamblers. It needs {} more {} to heal before you can start an operation here.".format(time_remaining, time_used)
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if not poi.is_district:
        response = "Oi, dumbass! You can't join an operation if you aren't in a district zone, first!"
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if user_data.life_state == ewcfg.life_state_juvenile:
        faction = ewcfg.psuedo_faction_gankers
    elif user_data.life_state == ewcfg.life_state_shambler:
        faction = ewcfg.psuedo_faction_shamblers
    else:
        response = "Hey idiot, it's called *Gankers Vs. Shamblers!* No gangsters, ghosts, or SlimeCorp shills allowed!"
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    # if faction == ewcfg.psuedo_faction_gankers and district_data.degradation == 0:
    # 	response = "This place is already fully rejuvenated! You'll have to try somewhere else."
    # 	return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
    # elif faction == ewcfg.psuedo_faction_shamblers and district_data.degradation == ewcfg.district_max_degradation:
    # 	response = "This place is already fully shambled! You'll have to try somewhere else."
    # 	return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
    if poi.id_poi in [ewcfg.poi_id_juviesrow, ewcfg.poi_id_rowdyroughhouse, ewcfg.poi_id_copkilltown]:
        response = "This place is too heavily guarded. Trying to pull of an operation here strikes you as downright stupid."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
    elif poi.id_poi == ewcfg.poi_id_thevoid:
        response = "Wow, great idea shithead, this sure is prime real estate you're trying to take over here in the middle of fucking nowhere. Try somewhere else."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
    elif poi.id_poi in [ewcfg.poi_id_assaultflatsbeach, ewcfg.poi_id_oozegardens]:
        response = "It would be reckless to try and start an operation so close to the base of the {}. You'll have to try somewhere else.".format('Garden Gankers' if poi.id_poi == ewcfg.poi_id_oozegardens else 'Shamblers')
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    in_operation, op_poi = hunt_utils.gvs_check_if_in_operation(user_data)
    if in_operation:
        if op_poi != user_data.poi:
            response = "You're already in an operation! If you wanna add another {}, you'll have to head to {}, first!".format('seed packet' if faction == ewcfg.psuedo_faction_gankers else 'tombstone', op_poi)
            return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if cmd.tokens_count < 2:
        response = "You need to select a {} first, dummy!".format('seed packet' if faction == ewcfg.psuedo_faction_gankers else 'tombstone')
    else:
        selected_item = ewutils.flattenTokenListToString(cmd.tokens[1:])

        # if faction == ewcfg.psuedo_faction_gankers:
        # 	choices = seedpackets
        # else:
        # 	choices = tombstones
        #
        # found_choice = False
        # for choice in choices:
        # 	if selected_item in choice:
        # 		selected_item = choice
        # 		found_choice = True
        # 		break
        # 	else:
        # 		response = "That's not a valid {} you can select, bitch.".format('seed packet' if faction == ewcfg.psuedo_faction_gankers else 'tombstone')
        #
        # if not found_choice:
        # 	return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

        item_sought = bknd_item.find_item(item_search=selected_item, id_user=user_data.id_user, id_server=user_data.id_server, item_type_filter=ewcfg.it_item)

        if item_sought != None:
            item = EwItem(id_item=item_sought.get('id_item'))
            item_props = item.item_props

            id_item = item_props.get('id_item')
            if id_item != None:
                if faction == ewcfg.psuedo_faction_gankers and id_item not in seedpackets:
                    response = "That's not a valid seed packet you can select, bitch."
                    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                elif faction == ewcfg.psuedo_faction_shamblers and id_item not in tombstones:
                    response = "That's not a valid tombstone you can select, bitch."
                    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
            else:
                response = "That's not a valid {} you can select, bitch.".format('seed packet' if faction == ewcfg.psuedo_faction_gankers else 'tombstone')
                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

            if item_props.get('brainpower') != None:
                brainpower = int(item_props.get('brainpower'))  # Only for tombstones
            else:
                brainpower = 0

            enemytype = item_props.get('enemytype')

            is_duplicate = hunt_utils.gvs_check_operation_duplicate(user_data.id_user, user_data.poi, enemytype, faction)

            if is_duplicate:
                if faction == ewcfg.psuedo_faction_gankers:
                    response = "What the hell are you doing? You've already selected that seed packet!"
                else:
                    response = "Someone else already put down that tombstone."
                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

            if faction == ewcfg.psuedo_faction_shamblers:
                if district_data.horde_cooldown > time_now:
                    response = "You gotta wait another {} seconds before you can add another tombstone. Your zombie bones ain't what they used to be...".format(district_data.horde_cooldown - time_now)
                    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                else:
                    district_data.horde_cooldown = time_now + brainpower
                    district_data.persist()

            limit_reached, current_limit = hunt_utils.gvs_check_operation_limit(user_data.id_user, user_data.poi, enemytype, faction)

            if limit_reached:
                if faction == ewcfg.psuedo_faction_gankers:
                    response = "You can't select more than 6 seed packets at a time!"
                else:
                    response = "There's not enough room for your tombstone! **(Current Tombstone Limit: {})**".format(current_limit)
                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

            # await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "Are you sure? **!accept** or **!refuse**."))

            # # Wait for an answer
            # accepted = False
            # try:
            # 	message = await cmd.client.wait_for_message(timeout=10, author=cmd.message.author, check=ewutils.check_accept_or_refuse)
            #
            # 	if message != None:
            # 		if message.content.lower() == "!accept":
            # 			accepted = True
            # 		if message.content.lower() == "!refuse":
            # 			accepted = False
            # except:
            # 	accepted = False
            accepted = True

            if accepted:

                # Lock juveniles into the district for garden ops
                if faction == ewcfg.psuedo_faction_gankers:
                    ewutils.moves_active[user_data.id_user] = 0
                    ewutils.active_restrictions[user_data.id_user] = 4

                # If there are no player-generated operations, then the bot will simply spawn in ones automatically.
                enemyfaction = ewcfg.psuedo_faction_gankers if faction == ewcfg.psuedo_faction_shamblers else ewcfg.psuedo_faction_shamblers
                opposing_ops = bknd_core.execute_sql_query("SELECT enemytype FROM gvs_ops_choices WHERE district = '{}' AND faction = '{}'".format(user_data.poi, enemyfaction))
                if len(opposing_ops) == 0:
                    hunt_utils.gvs_insert_bot_ops(user_data.id_server, user_data.poi, enemyfaction)
                # print('spawning in bot ops...')

                if in_operation:
                    if faction == ewcfg.psuedo_faction_gankers:
                        response = "You add your {} to the Garden Op".format(item_props.get('item_name'))
                    else:
                        response = "You add your {} to the Graveyard Op".format(item_props.get('item_name'))
                        response += "\n(You and your allies can add another one in {} seconds.)".format(brainpower)
                else:
                    if faction == ewcfg.psuedo_faction_gankers:
                        response = "You ready up for a Garden Op in {} with your {}. *Ready, set, PLANT!*".format(poi.str_name, item_props.get('item_name'))
                        district_data.gaiaslime += 50
                        district_data.persist()
                    else:
                        response = "You place down your {} in {} and get ready for a Graveyard Op. *Ready, set, BRRRRAAAAAIIINNNNZZZZ!*".format(item_props.get('item_name'), poi.str_name)
                        response += "\n(You and your allies can add another one in {} seconds.)".format(brainpower)

                # durability = int(item_props.get('durability'))

                if faction == ewcfg.psuedo_faction_shamblers:
                    shambler_stock = int(item_props.get('stock'))
                else:
                    shambler_stock = 0

                # if durability > 1:
                # 	item.item_props['durability'] = durability - 1
                # 	item.persist()
                # 	response += "\n(Your {}'s durability has been lowered)".format(item_props.get('item_name'))
                # else:
                # 	bknd_item.item_delete(item.id_item)
                # 	response += "\n(Your {} has been used up completely)".format(item_props.get('item_name'))

                op_data = EwOperationData(
                    id_user=user_data.id_user,
                    district=user_data.poi,
                    enemytype=enemytype,
                    faction=faction,
                    id_item=item_sought.get('id_item'),
                    shambler_stock=shambler_stock
                )
                op_data.persist()

            else:
                response = "Well, perhaps some other time, then."

        else:
            response = "Are you sure you have that {}? Try using **!inv**".format('seed packet' if faction == ewcfg.psuedo_faction_gankers else 'tombstone')

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def gvs_leave_operation(cmd):
    user_data = EwUser(member=cmd.message.author)

    if user_data.life_state == ewcfg.life_state_juvenile:
        faction = ewcfg.psuedo_faction_gankers
    elif user_data.life_state == ewcfg.life_state_shambler:
        faction = ewcfg.psuedo_faction_shamblers
    else:
        return

    in_operation, op_poi = hunt_utils.gvs_check_if_in_operation(user_data)
    if not in_operation:
        response = "You aren't even *in* an operation."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "Are you sure? **!accept** or **!refuse**."))

    # Wait for an answer
    accepted = False
    try:

        message = await cmd.client.wait_for('message', timeout=30, check=lambda message: message.author == cmd.message.author and message.content.lower() in [ewcfg.cmd_accept, ewcfg.cmd_refuse])

        if message != None:
            if message.content.lower() == "!accept":
                accepted = True
            if message.content.lower() == "!refuse":
                accepted = False
    except:
        accepted = False

    if accepted:
        ewutils.active_restrictions[user_data.id_user] = 0

        items = bknd_core.execute_sql_query("SELECT id_item FROM gvs_ops_choices WHERE id_user = '{}'".format(user_data.id_user))
        bknd_core.execute_sql_query("DELETE FROM gvs_ops_choices WHERE id_user = '{}'".format(user_data.id_user))
        await bknd_hunt.delete_all_enemies(cmd=None, query_suffix="AND owner = '{}' AND poi = '{}'".format(user_data.id_user, user_data.poi), id_server_sent=user_data.id_server)

        response = "You drop out of your {} Op in {}.".format('Garden' if faction == ewcfg.psuedo_faction_gankers else 'Graveyard', op_poi)

        for item in items:
            item_data = EwItem(id_item=item)
            durability = int(item_data.item_props.get('durability'))

            if faction == ewcfg.psuedo_faction_gankers:
                if durability > 1:
                    item_data.item_props['durability'] = durability - 1
                    item_data.persist()
                    response += "\n(Your {}'s durability has been lowered)".format(item_data.item_props.get('item_name'))
                else:
                    bknd_item.item_delete(item)
                    response += "\n(Your {} has been used up completely)".format(item_data.item_props.get('item_name'))

            else:
                # To prevent shamblers from re-stocking operations with tombstones, they are destroyed upon leaving a graveyard op.
                bknd_item.item_delete(item)
                response += "\n(Your {} has been used up completely)".format(item_data.item_props.get('item_name'))

        response += "\nAll your Gaiaslimeoids in {} wilt and die.".format(op_poi) if faction == ewcfg.psuedo_faction_gankers else "All the shamblers belonging to your tombstone in {} fall apart and collapse onto the ground.".format(op_poi)

    else:
        response = "Well, perhaps some other time, then."

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def gvs_check_operations(cmd):
    if cmd.tokens_count == 1:
        operations = bknd_core.execute_sql_query("SELECT district, faction FROM gvs_ops_choices GROUP BY district;")

        response = "There are currently no Garden Ops or Graveyard Ops at this time."
        if len(operations) > 0:
            response = ""
            for op in operations:
                response += "\nThere are operations taking place in {}.".format(poi_static.id_to_poi.get(op[0]).str_name)

    elif cmd.tokens_count > 1:
        checked_district = ewutils.flattenTokenListToString(cmd.tokens[1:])
        district = poi_static.id_to_poi.get(checked_district)

        if district == None or not district.is_district:
            response = "That's not a valid district that you can check"
        else:
            operations = bknd_core.execute_sql_query("SELECT enemytype FROM gvs_ops_choices WHERE district = '{}' GROUP BY enemytype".format(district.id_poi))

            if len(operations) > 0:
                gaias = bknd_core.execute_sql_query("SELECT enemytype FROM gvs_ops_choices WHERE district = '{}' AND faction = 'gankers' GROUP BY enemytype".format(district.id_poi))
                shamblers = bknd_core.execute_sql_query("SELECT enemytype FROM gvs_ops_choices WHERE district = '{}' AND faction = 'shamblers' GROUP BY enemytype".format(district.id_poi))

                response = "In {}, the currently selected seed packets and tombstones include...\n".format(district.str_name)
                response += "**GAIASLIMEOIDS**"
                for gaia in gaias:
                    response += "\n{}".format(gaia[0])
                response += "\n**SHAMBLERS**"
                for shambler in shamblers:
                    response += "\n{}".format(shambler[0])

            else:
                response = "There aren't any operations going on in that district."

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def gvs_plant_gaiaslimeoid(cmd):
    seedpackets = static_items.seedpacket_ids
    time_now = int(time.time())

    user_data = EwUser(member=cmd.message.author)
    poi = poi_static.id_to_poi.get(user_data.poi)
    district_data = EwDistrict(district=user_data.poi, id_server=user_data.id_server)

    if not user_data.life_state == ewcfg.life_state_juvenile:
        response = "Only Juveniles of pure heart can lay down Gaiaslimeoids on the field."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if ewutils.channel_name_is_poi(cmd.message.channel.name) == False:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You must {} in a zone's channel.".format(cmd.tokens[0])))
    if not poi.is_district:
        response = "You can't plant a Gaiaslimeoid here, dummy!"
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    in_operation, op_poi = hunt_utils.gvs_check_if_in_operation(user_data)
    if not in_operation:
        response = "You aren't even *in* an operation."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
    elif user_data.poi != op_poi:
        response = "You can't plant a Gaiaslimeoid here, dummy! Try heading to {}.".format(poi_static.id_to_poi.get(op_poi).str_name)
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if cmd.tokens_count < 3:
        response = "You need to select a coordinate and seed packet, dummy!"
    else:
        coord = cmd.tokens[1].upper()
        selected_item = ewutils.flattenTokenListToString(cmd.tokens[2:])
        valid_coord = False

        for row in ewcfg.gvs_valid_coords_gaia:
            if coord in row:
                valid_coord = True
                break

        if not valid_coord:
            response = "That's not a valid coordinate, bitch."
            return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

        # choices = seedpackets
        #
        # found_choice = False
        # for choice in choices:
        # 	if selected_item in choice:
        # 		selected_item = choice
        # 		found_choice = True
        # 		break
        # 	else:
        # 		response = "That's not a valid seed packet you can select, bitch. (Hint: !plant [coord] [seed packet])"
        #
        # if not found_choice or invalid_coord:
        # 	return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

        item_sought = bknd_item.find_item(item_search=selected_item, id_user=cmd.message.author.id, id_server=user_data.id_server, item_type_filter=ewcfg.it_item)
        if item_sought != None:
            item = EwItem(id_item=item_sought.get('id_item'))
            item_props = item.item_props

            id_item = item_props.get('id_item')
            if id_item != None:
                if id_item not in seedpackets:
                    response = "That's not a valid seed packet you can select, bitch."
                    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
            else:
                response = "That's not a valid seed packet you can select, bitch."
                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

            enemytype = item_props.get('enemytype')
            cooldown = int(item_props.get('cooldown'))
            cost = int(item_props.get('cost'))
            time_nextuse = int(item_props.get('time_nextuse'))

            if cost > district_data.gaiaslime:
                response = "There's not enough Gaiaslime to go around! ({}/{})".format(district_data.gaiaslime, cost)
            elif time_nextuse > time_now:
                response = "You need to wait {} seconds before you can plant that Gaiaslimeoid down.".format(time_nextuse - time_now)
            else:
                item.item_props['time_nextuse'] = time_now + cooldown
                item.persist()

                gaias_in_coord = hunt_utils.gvs_get_gaias_from_coord(user_data.poi, coord)

                if len(gaias_in_coord) > 0:
                    for gaia in gaias_in_coord.keys():
                        enemy_data = EwEnemy(id_enemy=gaias_in_coord[gaia])

                        if enemytype == gaia:
                            if gaia in ewcfg.repairable_gaias:
                                enemy_data.slimes = enemy_data.initialslimes
                                district_data.gaiaslime -= cost
                                enemy_data.persist()
                                district_data.persist()

                                response = "The {} in {} was fully repaired!".format(enemy_data.display_name, enemy_data.gvs_coord)
                                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                            else:
                                response = "There's already a {} in that coordinate!".format(enemy_data.display_name)
                                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                        else:
                            if enemy_data.enemy_props.get('joybean') == 'true' and enemytype == ewcfg.enemy_type_gaia_joybeans:
                                response = "A Joybean has already been planted there."
                                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                            elif enemy_data.enemy_props.get('metallicaps') == 'true' and enemytype == ewcfg.enemy_type_gaia_metallicaps:
                                response = "A Metallicap has already been planted there."
                                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                            elif enemy_data.enemy_props.get('aushucks') == 'true' and enemytype == ewcfg.enemy_type_gaia_aushucks:
                                response = "An Aushuck has already been planted there."
                                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
                            else:
                                response = "There's already a {} in that coordinate!".format(enemy_data.display_name)
                                return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

                    district_data.gaiaslime -= cost
                    district_data.persist()

                    resp_cont = hunt_utils.spawn_enemy(
                        id_server=user_data.id_server,
                        pre_chosen_type=enemytype,
                        pre_chosen_level=50,
                        pre_chosen_poi=user_data.poi,
                        pre_chosen_identifier='',
                        pre_chosen_faction=ewcfg.psuedo_faction_gankers,
                        pre_chosen_owner=user_data.id_user,
                        pre_chosen_coord=coord,
                        manual_spawn=True,
                    )

                    return await resp_cont.post()

                else:
                    if enemytype == ewcfg.enemy_type_gaia_metallicaps:
                        response = "Metallicaps must be planted on top of attacking Gaiaslimeoids."
                    elif enemytype == ewcfg.enemy_type_gaia_aushucks:
                        response = "Aushucks must first be planted on top of existing Gaiaslimeoids."
                    else:
                        district_data.gaiaslime -= cost
                        district_data.persist()

                        resp_cont = hunt_utils.spawn_enemy(
                            id_server=user_data.id_server,
                            pre_chosen_type=enemytype,
                            pre_chosen_level=50,
                            pre_chosen_poi=user_data.poi,
                            pre_chosen_identifier='',
                            pre_chosen_faction=ewcfg.psuedo_faction_gankers,
                            pre_chosen_owner=user_data.id_user,
                            pre_chosen_coord=coord,
                            manual_spawn=True,
                        )

                        return await resp_cont.post()

        else:
            response = "Are you sure you have that seed packet? Try using **!inv**"

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def almanac(cmd):
    if not cmd.tokens_count > 1:
        enemy_counter = 0
        enemy_total = 0
        # list off help topics to player at college
        response = "(Use !almanac [enemy] to learn about a shambler/gaiaslimeoid. Example: '!almanac defaultshambler')\n\nWhat would you like to learn about? Topics include: \n"

        # display the list of topics in order
        enemies = ewcfg.gvs_enemies

        # enemies = ewcfg.cmd_gvs_almanac.keys()
        for enemy in enemies:
            enemy_counter += 1
            enemy_total += 1
            response += "**{}**".format(enemy)
            if enemy_total != len(enemies):
                response += ", "

            if enemy_counter == 5:
                enemy_counter = 0
                response += "\n"

    else:
        enemytype = ewutils.flattenTokenListToString(cmd.tokens[1:])
        if enemytype in ewcfg.gvs_almanac:
            response = ewcfg.gvs_almanac[enemytype]
        else:
            response = 'ENDLESS WAR questions your belief in the existence of such a shambler or gaiaslimeoid. Try referring to the ones in the list again by using just !almanac.'

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


""" Lets shamblers start an event in DMs to get brains """


async def gvs_searchforbrainz(cmd):
    user_data = EwUser(member=cmd.message.author)

    if user_data.life_state != ewcfg.life_state_shambler:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You're not based enough to do that."))

    if user_data.poi != ewcfg.poi_id_slimesea:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You have to {} in the Slime Sea.".format(ewcfg.cmd_gvs_searchforbrainz)))

    time_now = int(time.time())

    if user_data.gvs_time_lastshambaquarium + ewcfg.cd_gvs_searchforbrainz >= time_now:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You'll have to rest for a while before searching for brainz again."))

    event_props = {}
    event_props['id_user'] = cmd.message.author.id
    event_props['brains_grabbed'] = 1
    event_props['captcha'] = ewutils.generate_captcha(length=1, user_data=user_data)
    event_props['channel'] = cmd.message.author.id

    # DM user
    response = poi_static.event_type_to_def.get(ewcfg.event_type_shambaquarium).str_event_start.format(ewcfg.cmd_gvs_grabbrainz, ewutils.text_to_regional_indicator(event_props['captcha']))
    try:
        await fe_utils.send_message(cmd.client, cmd.message.author, response)
    except fe_utils.discord.errors.Forbidden:
        response = "You have to allow ENDLESS WAR to DM you to search for brainz!"
        return await fe_utils.send_message(cmd.client, cmd.message.channel, response)

    user_data = EwUser(member=cmd.message.author)

    # check if the user's state hasn't changed just in case
    if user_data.life_state != ewcfg.life_state_shambler:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You're not based enough to do that."))

    if user_data.poi != ewcfg.poi_id_slimesea:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You have to {} in the Slime Sea.".format(ewcfg.cmd_gvs_searchforbrainz)))

    bknd_worldevent.create_world_event(
        id_server=user_data.id_server,
        event_type=ewcfg.event_type_shambaquarium,
        time_activate=time_now,
        time_expir=time_now + 60,  # 1 minute
        event_props=event_props
    )

    user_data.gvs_time_lastshambaquarium = time_now
    user_data.persist()


""" Command for shamblers to get brains in the shambaquarium event """


async def gvs_grabbrainz(cmd):
    if not isinstance(cmd.message.channel, fe_utils.discord.channel.DMChannel):
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You have to {} in DMs.".format(ewcfg.cmd_gvs_grabbrainz)))

    user_data = EwUser(id_user=cmd.message.author.id, id_server=cmd.guild.id)

    if user_data.life_state != ewcfg.life_state_shambler:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You're not based enough to do that."))

    if user_data.poi != ewcfg.poi_id_slimesea:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You have to {} in the Slime Sea.".format(ewcfg.cmd_gvs_grabbrainz)))

    # look for a shambaquarium event belonging to this player
    world_events = bknd_worldevent.get_world_events(id_server=cmd.guild.id)
    for id_event in world_events:
        if world_events.get(id_event) == ewcfg.event_type_shambaquarium:
            event_data = EwWorldEvent(id_event=id_event)
            if int(event_data.event_props.get('id_user')) == user_data.id_user:

                captcha = ewutils.flattenTokenListToString(cmd.tokens[1:]).lower()

                if event_data.event_props.get('captcha').lower() == captcha:
                    event_data.event_props['brains_grabbed'] = int(event_data.event_props['brains_grabbed']) + 1
                    captcha_length = int(event_data.event_props['brains_grabbed'])
                    event_data.event_props['captcha'] = ewutils.generate_captcha(length=captcha_length if captcha_length < 8 else 8, user_data=user_data)
                    event_data.persist()

                    user_data.gvs_currency += ewcfg.brainz_per_grab
                    user_data.persist()

                    response = "You grabbed {} brainz! Baaaaaased! New captcha: ".format(ewcfg.brainz_per_grab) + ewutils.text_to_regional_indicator(event_data.event_props['captcha'])
                    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

                else:
                    event_data.event_props['captcha'] = ewutils.generate_captcha(length=int(event_data.event_props['brains_grabbed']), user_data=user_data)
                    event_data.persist()
                    response = "Missed! That was pretty cringe dude... New captcha: " + ewutils.text_to_regional_indicator(event_data.event_props['captcha'])
                    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

            # break

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You have to {} before trying to grab any brainz!".format(ewcfg.cmd_gvs_searchforbrainz)))


""" Lets shamblers enter the slime sea"""


async def gvs_dive(cmd):
    user_data = EwUser(member=cmd.message.author)

    if user_data.life_state != ewcfg.life_state_shambler:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You're not based enough to do that."))

    if user_data.poi != ewcfg.poi_id_nuclear_beach_edge:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You have to {} at the edge of Nuclear Beach.".format(ewcfg.cmd_gvs_dive)))

    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You begin swimming towards the Slime Sea."), delete_after=15)

    await asyncio.sleep(15)

    user_data = EwUser(member=cmd.message.author)
    user_data.poi = ewcfg.poi_id_slimesea
    user_data.persist()

    slimesea = poi_static.id_to_poi.get(ewcfg.poi_id_slimesea)
    sea_channel = fe_utils.get_channel(cmd.guild, slimesea.channel)
    await fe_utils.send_message(cmd.client, sea_channel, fe_utils.formatMessage(cmd.message.author, "You arrive in the Slime Sea."), delete_after=10)

    await ewrolemgr.updateRoles(client=cmd.client, member=cmd.message.author)


""" Lets shamblers exit the slime sea"""


async def gvs_resurface(cmd):
    user_data = EwUser(member=cmd.message.author)

    if user_data.life_state != ewcfg.life_state_shambler:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You're not based enough to do that."))

    if user_data.poi != ewcfg.poi_id_slimesea:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You have to {} at the Slime Sea.".format(ewcfg.cmd_gvs_resurface)))

    await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You begin swimming towards the Nuclear Beach."), delete_after=15)

    await asyncio.sleep(15)

    user_data = EwUser(member=cmd.message.author)
    user_data.poi = ewcfg.poi_id_nuclear_beach_edge
    user_data.persist()

    beach = poi_static.id_to_poi.get(ewcfg.poi_id_nuclear_beach_edge)
    beach_channel = fe_utils.get_channel(cmd.guild, beach.channel)
    await fe_utils.send_message(cmd.client, beach_channel, fe_utils.formatMessage(cmd.message.author, "You arrive in the Nuclear Beach."), delete_after=10)

    await ewrolemgr.updateRoles(client=cmd.client, member=cmd.message.author)


""" Sell a potted gaiaslimeoid to Hortisolis """


async def gvs_sell_gaiaslimeoid(cmd):
    user_data = EwUser(member=cmd.message.author)

    if user_data.life_state == ewcfg.life_state_shambler:
        response = "You lack the higher brain functions required to {}.".format(cmd.tokens[0])
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    # Only at the Atomic Forest
    if user_data.poi != ewcfg.poi_id_og_farms:
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, "You have to be in the Atomic Forest to sell your Gaiaslimeoids."))

    item_search = ewutils.flattenTokenListToString(cmd.tokens[1:])
    item_sought = bknd_item.find_item(item_search=item_search, id_user=cmd.message.author.id, id_server=cmd.guild.id, item_type_filter=ewcfg.it_item)

    if item_sought:
        gaiaslimeoid = EwItem(id_item=item_sought.get('id_item'))

        if gaiaslimeoid.item_props.get('id_item') != ewcfg.item_id_gaiaslimeoid_pot:
            response = "Hortisolis politely refuses that item. He informs you that it is not a potted Gaiaslimeoid."
            return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

        slime_gain = 20000 * int(gaiaslimeoid.item_props.get('size'))

        gaia_type = gaiaslimeoid.item_props.get('gaiaslimeoid')

        response = 'Hortisolis speaks in a boisterous manner:\n"FOR THOUST {} GAIASLIMEOID, I SUBMIT {} SLIME. DO YOU {}, OR WOULD YOU RATHER {}?"'.format(gaia_type, slime_gain, ewcfg.cmd_accept, ewcfg.cmd_refuse)
        await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

        # Wait for an answer
        accepted = False
        try:
            msg = await cmd.client.wait_for('message', timeout=30, check=lambda message: message.author == cmd.message.author and message.content.lower() in [ewcfg.cmd_accept, ewcfg.cmd_refuse])

            if msg != None:
                if msg.content == ewcfg.cmd_accept:
                    accepted = True
        except:
            accepted = False

        gaiaslimeoid = EwItem(id_item=item_sought.get('id_item'))
        # cancel deal if the gaiaslimeoid is no longer in user's inventory
        if gaiaslimeoid.id_owner != str(user_data.id_user):
            accepted = False

        if accepted:
            user_data = EwUser(member=cmd.message.author)
            user_data.change_slimes(slime_gain)
            user_data.persist()

            bknd_item.item_delete(gaiaslimeoid.id_item)

            response = "Hortisolis gives you {} slime for your {} Gaiaslimeoid.".format(slime_gain, gaiaslimeoid.item_props.get('gaiaslimeoid'))

        else:
            response = '"A PITY, PERHAPS YOU WILL FIND SOME USE FOR IT ELSEWHERE. PRITHEE BE CAREFUL!"'

    else:
        response = "Are you sure you have that Gaiaslimeoid?"

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


""" Dig up a gaiaslimeoid """


async def dig(cmd):  # TODO  zen garden functionality

    if cmd.tokens_count < 2:
        response = 'Specify which coordinate you want to dig up.'
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    user_data = EwUser(member=cmd.message.author)

    if user_data.life_state == ewcfg.life_state_shambler:
        response = "You lack the higher brain functions required to {}.".format(cmd.tokens[0])
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    weapon_item = EwItem(id_item=user_data.weapon)

    if weapon_item.item_props.get("weapon_type") != ewcfg.weapon_id_shovel:
        response = "You can't dig Gaiaslimeoids without a shovel, dumbass. Buy one from Hortisolis at the Atomic Forest in Ooze Gardens Farms!"
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    coord = cmd.tokens[1].upper()
    is_garden = False

    # Look for gaiaslimeoid
    gaias = hunt_utils.gvs_get_gaias_from_coord(user_data.poi, coord)

    dig_low_priority = [ewcfg.enemy_type_gaia_rustealeaves]
    dig_mid_priority = []
    dig_high_priority = [ewcfg.enemy_type_gaia_steelbeans]

    # ID of gaiaslimeoid found
    dig_target = None

    for enemy_id in ewcfg.gvs_enemies_gaiaslimeoids:
        if enemy_id not in dig_low_priority and enemy_id not in dig_high_priority:
            dig_mid_priority.append(enemy_id)

    type_to_id_map = {}
    for id in gaias.keys():
        type = gaias[id]
        type_to_id_map[type] = id

    for target in dig_high_priority:
        if target in type_to_id_map.keys():
            dig_target = type_to_id_map[target]

    for target in dig_mid_priority:
        if target in type_to_id_map.keys():
            dig_target = type_to_id_map[target]

    for target in dig_low_priority:
        if target in type_to_id_map.keys():
            dig_target = type_to_id_map[target]

    # is_garden = if it was a garden

    if dig_target is None:
        response = "There are no Gaiaslimeoids here."
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    if not is_garden:

        enemy = EwEnemy(id_server=user_data.id_server, id_enemy=dig_target)
        bknd_hunt.delete_enemy(enemy)

        if random.random() < 0.8:  # 90% chance to fail
            response = "You dig up a {} Gaiaslimeoid."
            return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

        bknd_item.item_create(
            item_type=ewcfg.it_item,
            id_user=cmd.message.author.id,
            id_server=cmd.guild.id,
            item_props={
                'id_item': ewcfg.item_id_gaiaslimeoid_pot,
                'item_name': "Pot containing a {} Gaiaslimeoid".format(enemy.display_name),
                'item_desc': "It's a pot with a {} foot-tall {} Gaiaslimeoid. You can place it in a zen garden or sell it to Hortisolis.".format("{size}", enemy.display_name),
                'time_lastslimed': int(time.time()),
                'size': 1,
                'gaiaslimeoid': enemy.enemytype
            }
        )

        response = "You dig up a {} Gaiaslimeoid and place it in a pot!".format(enemy.display_name)

    else:
        response = "Placeholder zen garden dig"
    # change owner

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def gvs_progress(cmd):
    op_districts = []
    response = ""

    for poi in poi_static.poi_list:
        # if poi.is_district and not poi.id_poi in [ewcfg.poi_id_rowdyroughhouse, ewcfg.poi_id_copkilltown, ewcfg.poi_id_juviesrow, ewcfg.poi_id_oozegardens, ewcfg.poi_id_assaultflatsbeach, ewcfg.poi_id_thevoid]:
        if poi.is_district:
            op_districts.append(poi.id_poi)

    degradation_data = bknd_core.execute_sql_query("SELECT district, degradation FROM districts WHERE district IN {} AND id_server = {}".format(tuple(op_districts), cmd.message.guild.id))

    non_degraded_districts = []
    degraded_districts = []

    for district in degradation_data:
        if district[1] == 0:
            non_degraded_districts.append(district[0])
        elif district[1] == ewcfg.district_max_degradation:
            degraded_districts.append(district[0])

    # non_degraded_districts = set(non_degraded_districts)
    # degraded_districts = set(degraded_districts)

    counter = 0
    response += "\n**Rejuvenated Districts**"
    for non_deg in non_degraded_districts:
        if counter % 5 == 0:
            response += "\n"

        poi = poi_static.id_to_poi.get(non_deg)
        counter += 1

        if counter != len(non_degraded_districts):
            response += "{}, ".format(poi.str_name)
        else:
            response += "and {}.".format(poi.str_name)

    counter = 0
    response += "\n**Shambled Districts**"
    for deg in degraded_districts:
        if counter % 5 == 0:
            response += "\n"

        poi = poi_static.id_to_poi.get(deg)
        counter += 1

        if counter != len(degraded_districts):
            response += "{}, ".format(poi.str_name)
        else:
            response += "and {}.".format(poi.str_name)

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def gvs_gaiaslime(cmd):
    user_data = EwUser(member=cmd.message.author)

    district_data = EwDistrict(district=user_data.poi, id_server=user_data.id_server)

    if district_data.gaiaslime > 0:
        response = "This district houses {} gaiaslime.".format(district_data.gaiaslime)
    else:
        response = "There is no gaiaslime to be found here."
    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def gvs_brainz(cmd):
    user_data = EwUser(member=cmd.message.author)

    response = "You have {} brainz.".format(user_data.gvs_currency)
    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


""" 
    DEBUG COMMANDS
"""


# Debug
async def set_slime(cmd):
    if not cmd.message.author.guild_permissions.administrator:
        return

    response = ""
    target = None

    if cmd.mentions_count != 1:
        response = "Invalid use of command. Example: !setslime @player 100"
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
    else:
        target = cmd.mentions[0]

    target_user_data = EwUser(id_user=target.id, id_server=cmd.guild.id)

    if len(cmd.tokens) > 2:
        new_slime = ewutils.getIntToken(tokens=cmd.tokens, allow_all=True)
        if new_slime == None:
            response = "Invalid number entered."
            return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

        new_slime -= target_user_data.slimes
    else:
        return

    if target_user_data != None:

        user_initial_level = target_user_data.slimelevel
        levelup_response = target_user_data.change_slimes(n=new_slime)

        was_levelup = True if user_initial_level < target_user_data.slimelevel else False

        if was_levelup:
            response += " {}".format(levelup_response)
        target_user_data.persist()

        response = "Set {}'s slime to {}.".format(target.display_name, target_user_data.slimes)
    else:
        return

    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


# Debug
async def check_stats(cmd):
    if not cmd.message.author.guild_permissions.administrator:
        return

    response = ""

    if cmd.mentions_count != 1:
        response = "Invalid use of command. Example: !checkstats @player "
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))
    else:
        target = cmd.mentions[0]

    target_user_data = EwUser(id_user=target.id, id_server=cmd.guild.id, data_level=2)

    if target_user_data != None:
        response = "They have {} attack, {}  defense, and {} speed.".format(target_user_data.attack, target_user_data.defense, target_user_data.speed)
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


# Give Brimstone Programmer role to a member
async def make_bp(cmd):
    return
    if EwUser(member=cmd.message.author).life_state != ewcfg.life_state_kingpin and not cmd.author_id.admin:
        return

    if cmd.mentions_count > 0:
        recipient = cmd.mentions[0]
    else:
        response = 'who?'
        return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))

    bp_role = None
    for role in cmd.guild.roles:
        if role.name == "Brimstone Programmer":
            bp_role = role
            break

    if bp_role:
        await recipient.add_roles(bp_role)
    else:
        ewutils.logMsg("Could not find Brimstone Programmer role.")


# pings user
async def ping_me(cmd):
    author = cmd.message.author
    user_data = EwUser(member=author)

    if ewutils.DEBUG or author.guild_permissions.administrator or user_data.life_state == ewcfg.life_state_kingpin:
        pass
    else:
        return

    try:
        requested_channel = cmd.tokens[1]
    except:
        return

    pinged_poi = poi_static.id_to_poi.get(requested_channel)
    channel = fe_utils.get_channel(cmd.guild, pinged_poi.channel)

    if pinged_poi != None:
        response = user_data.get_mention()
        return await fe_utils.send_message(cmd.client, channel, response)


async def shut_down_bot(cmd):
    if not cmd.message.author.guild_permissions.administrator:
        return await wep_cmds.suicide(cmd=cmd)

    ewutils.logMsg('Goodbye!')
    await asyncio.sleep(2)

    while True:
        sys.exit()

async def set_debug_option(cmd):
    response = ""
    if ewutils.DEBUG == True:
        if len(cmd.tokens) == 3:
            option = cmd.tokens[1]
            value = cmd.tokens[2]

            ewutils.DEBUG_OPTIONS.get(option)
            if option != None:
                if value == 'true':
                    ewutils.DEBUG_OPTIONS[option] = True
                    response = "{option} = {value}".format(option=option, value=value)

                elif value == 'false':
                    ewutils.DEBUG_OPTIONS[option] = False
                    response = "{option} = {value}".format(option=option, value=value)

                else:
                    response = "State whether debug option should be true or false."
            else:
                response = "Invalid debug option."
        else:
            response = "Command format: {} [option] [true/false]".format(ewcfg.cmd_set_debug_option)
    else:
        response = "ENDLESS WAR pays you no mind."
        
    return await fe_utils.send_response(response, cmd)





async def check_bot(cmd):
    if not cmd.message.author.guild_permissions.administrator:
        return

    ewutils.logMsg('TERMINATE is currently: {}'.format(ewutils.TERMINATE))

    return
    sys.exit()


"""
	Ban a player from participating in the game
"""


async def arrest(cmd):
    author = cmd.message.author

    if not author.guild_permissions.administrator:
        return

    if cmd.mentions_count == 1:
        member = cmd.mentions[0]
        user_data = EwUser(member=member)
        user_data.arrested = True
        user_data.poi = ewcfg.poi_id_thesphere
        user_data.change_slimes(n=- user_data.slimes)
        user_data.persist()

        response = "{} is thrown into one of the Juvenile Detention Center's high security solitary confinement spheres.".format(member.display_name)
        await ewrolemgr.updateRoles(client=cmd.client, member=member)
        await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


"""
	Allow a player to participate in the game again
"""


async def release(cmd):
    author = cmd.message.author

    if not author.guild_permissions.administrator:
        return

    if cmd.mentions_count == 1:
        member = cmd.mentions[0]
        user_data = EwUser(member=member)
        user_data.arrested = False
        user_data.poi = ewcfg.poi_id_juviesrow
        user_data.persist()

        response = "{} is released. But beware, the cops will be keeping an eye on you.".format(member.display_name)
        await ewrolemgr.updateRoles(client=cmd.client, member=member)
        await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def post_leaderboard(cmd):
    author = cmd.message.author
    if not author.guild_permissions.administrator:
        return
    user_data = EwUser(member=author)
    client = cmd.client
    server = client.get_guild(user_data.id_server)
    # Check for permissions
    await bknd_leaderboard.post_leaderboards(client=client, server=server)
    return await fe_utils.send_message(cmd.client, cmd.message.channel, "Yee-haw! Just refreshed that their leaderboard for ya sonny!")


"""
	Grants executive status
"""


async def promote(cmd):
    author = cmd.message.author

    if not author.guild_permissions.administrator:
        return

    if cmd.mentions_count == 1:
        member = cmd.mentions[0]
        user_data = EwUser(member=member)
        user_data.life_state = ewcfg.life_state_executive
        user_data.faction = ewcfg.faction_slimecorp
        user_data.persist()

        await ewrolemgr.updateRoles(client=cmd.client, member=member)


async def unban_manual(cmd):
    if not cmd.message.author.guild_permissions.administrator:
        return
    if len(cmd.tokens) == 2:
        id = int(cmd.tokens[1])
        user_obj = cmd.client.get_user(id)
        await cmd.guild.unban(user_obj)
        response = "Success"
    else:
        response = "Failure {}".format(len(cmd.mentions))
    await fe_utils.send_message(cmd.client, cmd.message.channel, response)


async def assign_status_effect(cmd = None, status_name = None, user_id = None, server_id = None):
    if status_name is not None:
        user_data = EwUser(id_server=server_id, id_user=user_id)
        response = user_data.applyStatus(id_status=status_name, source=user_id, id_target=user_id)
    else:
        if not cmd.message.author.guild_permissions.administrator or cmd.mentions_count == 0:
            return await cmd_utils.fake_failed_command(cmd)
        target = cmd.mentions[0]
        status_name = ewutils.flattenTokenListToString(cmd.tokens[2:])
        user_data = EwUser(member=target)
        response = user_data.applyStatus(id_status=status_name, source=user_data.id_user, id_target=user_data.id_user)
    return await fe_utils.send_message(cmd.client, cmd.message.channel, fe_utils.formatMessage(cmd.message.author, response))


async def print_cache(cmd):
    if not cmd.message.author.guild_permissions.administrator:
        return await cmd_utils.fake_failed_command(cmd)

    typelog = "*{}*: Current cache types are: \n".format(cmd.message.author.display_name)
    datalog = ""

    for cache in bknd_core.caches:
        typelog += "    {} with {} entries\n".format(cache.entry_type, len(cache.entries))
        datalog += "\n{} Cache contains:\n".format(cache.entry_type)

        entry_iter = 0
        for entry_id, entry in cache.entries.items():
            datalog += "    Identifier: {}, Data: {}\n".format(entry_id, entry)
            entry_iter += 1
            if entry_iter % 1000 == 0:
                ewutils.logMsg("Building string for cache, this may take a bit...")

    ewutils.logMsg(typelog)
    ewutils.logMsg(datalog)
