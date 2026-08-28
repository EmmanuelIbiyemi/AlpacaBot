

# This is where the main bot will trigger everything when the bot have meet it's requirements
# or when the bot detects that it's time to buy or sell

def order_botTrigger():
    try:


        return {
            "status":"success",
            "result":"" 
        }

    except Exception as e: 
        return {
            "status":"error",
            "reason":str(e)
        }

def position_botTrigger():
    try:


        return {
            "status":"success",
            "result":"" 
        }

    except Exception as e: 
        return {
            "status":"error",
            "reason":str(e)
        }