"""Kiswahili and English text for USSD screens and SMS. Kiswahili is the default.

Keep USSD screens under about 160 characters: many handsets cut longer screens.
"""

T = {
    # ---------- USSD: shared ----------
    "welcome_new": {
        "sw": "Karibu Mama Vuna Fresh\n1. Sajili ujauzito (mama)\n2. Jisajili kama msaidizi\n3. Dalili za hatari\n4. English",
        "en": "Welcome to Mama Vuna Fresh\n1. Register pregnancy\n2. Register as a helper\n3. Danger signs\n4. Kiswahili",
    },
    "invalid": {"sw": "Chaguo si sahihi. Piga {code} tena.", "en": "Invalid choice. Dial {code} again."},
    "more": {"sw": "98. Zaidi", "en": "98. More"},
    "bye": {"sw": "Asante. Mama Vuna Fresh.", "en": "Thank you. Mama Vuna Fresh."},
    "lang_set": {"sw": "Lugha imebadilishwa kuwa Kiswahili.", "en": "Language changed to English."},

    # ---------- USSD: mother registration ----------
    "ask_name": {"sw": "Andika jina lako kamili:", "en": "Enter your full name:"},
    "ask_age": {"sw": "Umri wako (miaka):", "en": "Your age (years):"},
    "ask_region": {"sw": "Chagua mkoa:", "en": "Choose your region:"},
    "ask_district": {"sw": "Chagua wilaya:", "en": "Choose your district:"},
    "ask_ward": {"sw": "Andika kata au mtaa wako:", "en": "Enter your ward or street:"},
    "ask_village": {"sw": "Andika kijiji au kitongoji:", "en": "Enter your village or hamlet:"},
    "ask_setting": {"sw": "Unaishi wapi?\n1. Kijijini\n2. Pembezoni mwa mji\n3. Mjini",
                    "en": "Where do you live?\n1. Village (rural)\n2. Edge of town\n3. Town / city"},
    "ask_livelihood": {"sw": "Kazi yako kuu:\n1. Mkulima\n2. Mfugaji\n3. Biashara/sokoni\n4. Kazi za nyumbani\n5. Kibarua/kiwanda\n6. Ofisi/mwajiriwa\n7. Nyingine",
                       "en": "Your main work:\n1. Farmer\n2. Livestock keeper\n3. Market/business\n4. Household\n5. Casual/factory\n6. Office/salaried\n7. Other"},
    "ask_crop": {"sw": "Zao lako kuu:", "en": "Your main crop:"},
    "ask_preg": {"sw": "Ujauzito:\n1. Najua tarehe ya kujifungua\n2. Najua miezi ya ujauzito",
                 "en": "Pregnancy:\n1. I know my due date\n2. I know how many months"},
    "ask_edd": {"sw": "Tarehe ya kujifungua (DD-MM-YYYY):", "en": "Due date (DD-MM-YYYY):"},
    "ask_months": {"sw": "Ujauzito una miezi mingapi? (1-9)", "en": "How many months pregnant? (1-9)"},
    "ask_consent": {
        "sw": "Taarifa zako zitaonekana kwa mhudumu wa afya na msaidizi atakayekusaidia tu.\n1. Nakubali\n2. Sikubali",
        "en": "Your details will be seen only by your health worker and the helper assigned to you.\n1. I agree\n2. I do not agree",
    },
    "bad_date": {"sw": "Tarehe si sahihi. Tumia mfano 20-01-2027. Piga {code} tena.",
                 "en": "Date not valid. Use e.g. 20-01-2027. Dial {code} again."},
    "bad_edd_range": {"sw": "Tarehe lazima iwe ndani ya miezi 10 ijayo. Piga {code} tena.",
                      "en": "The due date must be within the next 10 months. Dial {code} again."},
    "no_consent": {"sw": "Usajili umesitishwa. Unaweza kujisajili wakati wowote.",
                   "en": "Registration stopped. You can register any time."},
    "reg_done": {"sw": "Asante {first}! Umesajiliwa. Namba yako: {code}. Utapokea SMS yenye wiki zako za kupumzika.",
                 "en": "Thank you {first}! You are registered. Your number: {code}. You will get an SMS with your rest weeks."},
    "already_mother": {"sw": "Namba hii tayari imesajiliwa kama mama.", "en": "This number is already registered as a mother."},

    # ---------- USSD: registered mother ----------
    "mother_menu": {
        "sw": "Mama Vuna Fresh: {first}\n1. Hali yangu\n2. Omba msaada sasa\n3. Dalili za hatari\n4. Nimejifungua\n5. Badili tarehe ya kujifungua\n6. English",
        "en": "Mama Vuna Fresh: {first}\n1. My status\n2. Ask for help now\n3. Danger signs\n4. I have given birth\n5. Change due date\n6. Kiswahili",
    },
    "status_head": {"sw": "Wiki {week}. Kujifungua: {edd}\n", "en": "Week {week}. Due: {edd}\n"},
    "status_none": {"sw": "Hakuna kipindi kijacho cha kazi nzito.", "en": "No heavy-work period coming up."},
    "ask_help_type": {"sw": "Unahitaji msaada gani?", "en": "What help do you need?"},
    "help_sent": {"sw": "Ombi limetumwa kwa {helper}. Utapokea SMS akikubali.",
                  "en": "Request sent to {helper}. You will get an SMS when they accept."},
    "help_none": {"sw": "Hakuna msaidizi aliyepatikana sasa. Mhudumu wa afya amejulishwa na atakupigia.",
                  "en": "No helper is available now. Your health worker has been told and will call you."},
    "help_dup": {"sw": "Tayari una ombi la aina hii linaloshughulikiwa.", "en": "You already have a request of this kind in progress."},
    "birth_done": {"sw": "Hongera! Mhudumu wa afya atakutembelea. Endelea kupumzika wiki 6 zijazo.",
                   "en": "Congratulations! Your health worker will visit you. Keep resting for the next 6 weeks."},
    "edd_changed": {"sw": "Tarehe mpya ya kujifungua: {edd}. Wiki zako za kupumzika zimesasishwa.",
                    "en": "New due date: {edd}. Your rest weeks have been updated."},

    # ---------- USSD: danger signs ----------
    "danger_ask": {"sw": "Chagua dalili:", "en": "Choose the sign:"},
    "danger_done": {
        "sw": "NENDA KITUO CHA AFYA SASA. {facility}Mhudumu wa afya amejulishwa.",
        "en": "GO TO A HEALTH FACILITY NOW. {facility}Your health worker has been told.",
    },
    "danger_nonreg": {
        "sw": "Dalili hizi ni za hatari. Nenda kituo cha afya kilicho karibu SASA. Usisubiri.",
        "en": "These are danger signs. Go to the nearest health facility NOW. Do not wait.",
    },

    # ---------- USSD: helper ----------
    "helper_menu": {
        "sw": "Msaidizi: {first}\n1. Maombi yanayosubiri ({n})\n2. Saa zangu\n3. {avail}\n4. English",
        "en": "Helper: {first}\n1. Requests waiting ({n})\n2. My hours\n3. {avail}\n4. Kiswahili",
    },
    "avail_on": {"sw": "Sipatikani kwa sasa", "en": "Set me unavailable"},
    "avail_off": {"sw": "Napatikana tena", "en": "Set me available"},
    "avail_now_on": {"sw": "Sasa unapatikana kupokea maombi.", "en": "You are now available for requests."},
    "avail_now_off": {"sw": "Hutapokea maombi mapya mpaka urudi.", "en": "You will not get new requests until you return."},
    "helper_no_req": {"sw": "Hakuna ombi linalosubiri jibu lako.", "en": "No request is waiting for your reply."},
    "helper_req_line": {"sw": "{when}: {task}, {village}\n1. Nakubali\n2. Siwezi",
                        "en": "{when}: {task}, {village}\n1. Accept\n2. Decline"},
    "helper_hours": {"sw": "Saa zilizothibitishwa: {hours}. Asante kwa kusaidia jamii.",
                     "en": "Verified hours: {hours}. Thank you for helping your community."},
    "ask_group": {"sw": "Kikundi chako (andika jina) au 0 kama huna:", "en": "Your group name, or 0 if none:"},
    "ask_skills": {"sw": "Unaweza kusaidia nini?\n1. Shamba (kubeba, kupalilia)\n2. Nyumbani na maji\n3. Vyote",
                   "en": "What can you help with?\n1. Farm (carrying, weeding)\n2. Home and water\n3. Both"},
    "helper_consent": {
        "sw": "Utapokea SMS mama wa karibu akihitaji msaada. Namba yako itaonekana kwa mama utakayemsaidia.\n1. Nakubali\n2. Sikubali",
        "en": "You will get SMS when a mother nearby needs help. Your number will be shared with the mother you help.\n1. I agree\n2. I do not agree",
    },
    "ask_birth": {"sw": "Ulijifungua lini?\n1. Leo\n2. Jana\n3. Tarehe nyingine", "en": "When did you give birth?\n1. Today\n2. Yesterday\n3. Another date"},
    "ask_birth_date": {"sw": "Tarehe ya kujifungua (DD-MM-YYYY):", "en": "Date of birth (DD-MM-YYYY):"},
    "helper_reg_done": {"sw": "Asante {first}! Umesajiliwa kama msaidizi. Utapokea SMS mama wa karibu akihitaji msaada.",
                        "en": "Thank you {first}! You are registered as a helper. You will get an SMS when a mother nearby needs help."},
    "already_helper": {"sw": "Namba hii tayari imesajiliwa kama msaidizi.", "en": "This number is already registered as a helper."},

    # ---------- SMS ----------
    "sms_welcome": {
        "sw": "MAMA VUNA FRESH: Karibu {first} ({code}). Wiki zako za kupumzika:\n{windows}\nTutawaomba wasaidizi wa karibu kabla ya kila kipindi. Dalili za hatari: piga {ussd}.",
        "en": "MAMA VUNA FRESH: Welcome {first} ({code}). Your rest periods:\n{windows}\nWe will ask helpers nearby before each one. Danger signs: dial {ussd}.",
    },
    "sms_no_windows": {"sw": "Hakuna kipindi cha kazi nzito kilichopangwa sasa.", "en": "No heavy-work period scheduled yet."},
    "sms_alert": {
        "sw": "MAMA VUNA FRESH: Mama {first} ({place}) ni mjamzito na anahitaji msaada wa {task}, {start} hadi {end}. Jibu 1 kukubali au 2 kukataa.",
        "en": "MAMA VUNA FRESH: Mama {first} ({place}) is pregnant and needs help with {task}, {start} to {end}. Reply 1 to accept or 2 to decline.",
    },
    "sms_helper_thanks": {
        "sw": "Asante {first}! Mama {mother} ({phone}) atajulishwa. Mhudumu wa afya atathibitisha kazi ikikamilika.",
        "en": "Thank you {first}! Mama {mother} ({phone}) will be told. The health worker will confirm when the work is done.",
    },
    "sms_helper_declined": {"sw": "Sawa, asante. Tutamwomba mtu mwingine.", "en": "OK, thank you. We will ask someone else."},
    "sms_mother_matched": {
        "sw": "MAMA VUNA FRESH: {helper} ({group}) atakusaidia na {task} kuanzia {start}. Simu: {phone}. Pumzika: usibebe mizigo mizito wala kushika dawa za kuua wadudu.",
        "en": "MAMA VUNA FRESH: {helper} ({group}) will help you with {task} from {start}. Phone: {phone}. Rest: do not carry heavy loads or handle pesticides.",
    },
    "sms_verified": {
        "sw": "Kazi imethibitishwa: saa {hours}. Jumla yako: saa {total}. Asante kwa kumsaidia mama!",
        "en": "Work verified: {hours} hours. Your total: {total} hours. Thank you for helping a mother!",
    },
    "sms_chw_unfilled": {
        "sw": "MVF: Hakuna msaidizi kwa {mother} ({code}), {task} {start}. Tafadhali panga msaada. Simu ya mama: {phone}",
        "en": "MVF: No helper for {mother} ({code}), {task} {start}. Please arrange help. Mother's phone: {phone}",
    },
    "sms_chw_danger": {
        "sw": "MVF HATARI: {mother} ({code}), wiki {week}: {signs}. Mpigie sasa: {phone}. Kijiji: {place}.",
        "en": "MVF DANGER: {mother} ({code}), week {week}: {signs}. Call her now: {phone}. Village: {place}.",
    },
    "sms_chw_birth": {"sw": "MVF: {mother} ({code}) ameripoti kujifungua. Tafadhali mtembelee na ujaze taarifa za uzazi.",
                      "en": "MVF: {mother} ({code}) reported giving birth. Please visit and record the birth outcome."},
    "sms_no_pending": {"sw": "Hakuna ombi linalosubiri jibu lako kwa sasa.", "en": "There is no request waiting for your reply."},
    "sms_reply_help": {
        "sw": "Jibu 1 kukubali au 2 kukataa ombi. Piga {ussd} kwa huduma zaidi.",
        "en": "Reply 1 to accept or 2 to decline a request. Dial {ussd} for more.",
    },
    "sms_unknown": {"sw": "Karibu Mama Vuna Fresh. Piga {ussd} kujisajili.", "en": "Welcome to Mama Vuna Fresh. Dial {ussd} to register."},
    "sms_stopped": {"sw": "Hutapokea SMS zaidi. Tuma ANZA kurudi.", "en": "You will get no more SMS. Send START to come back."},
    "sms_restarted": {"sw": "Karibu tena Mama Vuna Fresh.", "en": "Welcome back to Mama Vuna Fresh."},
}

# Weekly pregnancy messages: (from_week, to_week, sw, en). General guidance only.
TIPS = [
    (1, 15, "Hudhuria kliniki mapema. Mpango wa afya unashauri angalau mahudhurio 8 wakati wa ujauzito. Meza vidonge vya madini chuma na folic asidi kama ulivyoelekezwa.",
     "Start antenatal care early. Aim for at least 8 clinic contacts in pregnancy. Take iron and folic acid tablets as advised."),
    (16, 23, "Kula vyakula mchanganyiko: mboga za majani, maharage, samaki au mayai, matunda. Kunywa maji safi ya kutosha.",
     "Eat a mix of foods: green vegetables, beans, fish or eggs, fruit. Drink enough safe water."),
    (24, 27, "Wiki chache zijazo utaanza kipindi cha kupumzika. Zungumza na kikundi chako kuhusu nani atakusaidia shambani na nyumbani.",
     "Your rest period starts in a few weeks. Talk with your group about who will help you on the farm and at home."),
    (28, 31, "Sasa uko miezi mitatu ya mwisho. Epuka kubeba mizigo mizito, kuinama muda mrefu na kushika dawa za kuua wadudu.",
     "You are now in the last three months. Avoid heavy loads, long bending and handling pesticides."),
    (32, 35, "Mtoto anapaswa kucheza kila siku. Akicheza kidogo au akiacha, nenda kituo cha afya mara moja.",
     "Your baby should move every day. If movements slow down or stop, go to a health facility at once."),
    (36, 38, "Andaa mpango wa kujifungua: kituo cha afya, usafiri, mtu wa kukusindikiza na fedha ya dharura.",
     "Prepare your birth plan: facility, transport, someone to go with you, and emergency money."),
    (39, 42, "Muda wa kujifungua umekaribia. Ukianza uchungu, chupa ikipasuka au ukitokwa damu, nenda kituo cha afya sasa.",
     "Birth is near. If labour starts, your waters break or you bleed, go to the health facility now."),
]


def t(lang: str, key: str, **kw) -> str:
    entry = T.get(key, {})
    s = entry.get(lang) or entry.get("sw") or key
    return s.format(**kw) if kw else s


def tip_for_week(week: int, lang: str):
    for a, b, sw, en in TIPS:
        if a <= week <= b:
            return (a, sw if lang == "sw" else en)
    return None
