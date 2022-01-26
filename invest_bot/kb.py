from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from invest_bot.messages import emoji_win, msg_top_investors, msg_top_partners


def top_info_ikb(items_count, screen_num=1, 
                 investors=False, 
                 partners=False):

    if investors:
        prefix = 'inv'
        callback_data = 'top_partners'
        button_text = msg_top_partners
    elif partners:
        prefix = 'part'
        callback_data = 'top_investors'
        button_text = msg_top_investors

    if screen_num == 1:
        if items_count < 26:
            ikb_list = []
        elif 26 <= items_count < 50:
            ikb_list = [InlineKeyboardButton(f'{emoji_win} 26-{items_count} »',
                                             callback_data=f'top_{prefix}_2')]
        elif items_count >= 50:
            ikb_list = [InlineKeyboardButton(f'{emoji_win} 26-50 »', 
                                             callback_data=f'top_{prefix}_2')]

    elif screen_num == 2:
        ikb_list = [InlineKeyboardButton(f'« {emoji_win} 1-25', 
                                         callback_data=f'top_{prefix}_1')]
        if 51 <= items_count < 75:
            ikb_list.append(
                InlineKeyboardButton(f'{emoji_win} 51-{items_count} »', 
                                     callback_data=f'top_{prefix}_3')
                )
        elif items_count >= 75:
            ikb_list.append(
                InlineKeyboardButton(f'{emoji_win} 51-75 »', 
                                     callback_data=f'top_{prefix}_3')
                )

    elif screen_num == 3:
        ikb_list = [InlineKeyboardButton(f'« {emoji_win} 26-50', 
                                         callback_data=f'top_{prefix}_2')]
        if 76 <= items_count < 100:
            ikb_list.append(
                InlineKeyboardButton(f'{emoji_win} 76-{items_count} »', 
                                     callback_data=f'top_{prefix}_4')
                )
        elif items_count >= 100:
            ikb_list.append(
                InlineKeyboardButton(f'{emoji_win} 76-100 »', 
                                     callback_data=f'top_{prefix}_4')
                )

    elif screen_num == 4:
        ikb_list = [InlineKeyboardButton(f'« {emoji_win} 51-75', 
                                         callback_data=f'top_{prefix}_3')]
    keyboard = [ikb_list]
    keyboard.append(
        [InlineKeyboardButton(button_text, callback_data=callback_data)]
        )
    return InlineKeyboardMarkup(keyboard)
