# Auto-apply skin for gAndy on login
gandy_auto_skin:
    type: world
    debug: true
    events:
        on player logs in:
        - if <player.name> == gAndy:
            - wait 10t
            - execute as_player "skin update"