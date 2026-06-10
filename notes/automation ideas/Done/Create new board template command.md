## Create a new board template command

I want to create a command that allows me to create new boards or update existing board with a json file containing predefined lists, cards, labels, and custom fields

Use C:\projects\AppDev\Planka\board_1784419684444013580_export.json as an example of input.

Command example

PT CreateBoard --Project <ProjectId> --Import C:\projects\AppDev\Planka\board_1784419684444013580_export.json
PT UpdateBoard --Board <BoardId> --Import C:\projects\AppDev\Planka\board_1784419684444013580_export.json

When updating only add what doesn't exist. Don't remove what is already there.
