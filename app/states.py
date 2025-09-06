from aiogram.fsm.state import StatesGroup, State


class Form(StatesGroup):
    business=State()
    test=State()
    stories_warmup=State()
    tripwire=State()
    weekly_warmup=State()
    universal=State()
    video_ideas=State()
    profile_design=State()
    posts_ideas=State()
    post_generation_theme=State()
    post_generation_input=State()
    post_generation_examples=State()
    style=State()
    signature=State()
    carousel_theme=State()
    theme_universal=State()
    reg_style=State()
    posts_idea=State()
    clear=State()