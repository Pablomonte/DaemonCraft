# Show coordinates in action bar for every player
execute as @a at @s run title @s actionbar ["",{"text":"X: ","color":"aqua"},{"score":{"name":"@s","objective":"dc_x"},"color":"white"},{"text":" Y: ","color":"aqua"},{"score":{"name":"@s","objective":"dc_y"},"color":"white"},{"text":" Z: ","color":"aqua"},{"score":{"name":"@s","objective":"dc_z"},"color":"white"}]

# Update coordinate scoreboards
execute as @a store result score @s dc_x run data get entity @s Pos[0]
execute as @a store result score @s dc_y run data get entity @s Pos[1]
execute as @a store result score @s dc_z run data get entity @s Pos[2]

# Auto-assign teams (join team matching their name, case-insensitive)
team join marcus Marcus
team join sarah Sarah
team join jin Jin
team join dave Dave
team join lisa Lisa
team join tommy Tommy
team join elena Elena
team join stevie Stevie
team join moss Moss
team join reed Reed
team join flint Flint
team join siqui Siqui

# Permanent glowing effect for all players (so you can see them through walls)
effect give @a minecraft:glowing 999999 0 true
