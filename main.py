from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
import database
import useful_functions

app = FastAPI()

inprogress_orders = {} 
rating_list = {}
orderlength = {}

@app.post("/")
async def handle_request(request : Request):
    payload = await request.json()

    intent = payload['queryResult']['intent']['displayName']
    parameters = payload['queryResult']['parameters']
    output_contexts = payload['queryResult']['outputContexts']

    session_id = useful_functions.extract_session_id(output_contexts[0]['name'])

    intent_handler_dict = {
        'new.order' : new_order,
        'order.add' : add_to_order,
        'order-remove' : remove_from_order,
        'order_complete' : complete_order,
        "trackorder-ongoing context" : track_order,
        "order.add.quantity" : add_more_quantity,
        "rate.order-ongoing" : rating_order,
        "rate.order-returnback" : rating_order
    }
    

    return intent_handler_dict[intent](parameters,session_id)

def new_order(parameters : dict, session_id : str):
    if session_id in inprogress_orders:
        inprogress_orders[session_id].clear()
    

def remove_from_order(parameters : dict, session_id : str ):
    if session_id not in inprogress_orders:
        return JSONResponse(content={
            "fulfillmentText" : "I'm having a trouble finding your order. Sorry! can you please order again?"
        })
    
    current_order = inprogress_orders[session_id]
    food_items = parameters["food-items"]
    quantities = parameters["number"]
    removed_items = []
    no_such_items = []
    fulfillment_text = ""

    if not quantities:
        for item in food_items:
            if item not in current_order:
                no_such_items.append(item)
            else:
                removed_items.append(item)
                del current_order[item]
        if len(removed_items) >0:
            fulfillment_text += f"Removed {", ".join(removed_items)} from your order."

        if len(no_such_items) >0:
            fulfillment_text += f"Your current order does not have {", ".join(no_such_items)}"
    else:
        for item, quantity in zip(food_items, quantities):
            if item not in current_order:
                no_such_items.append(item)
            elif quantity > float(current_order[item]):
                fulfillment_text += f"There are only {current_order[item]} {item} in your order."
            else:
                current_order[item] = str(float(current_order[item]) - quantity)
                fulfillment_text += f"Removed {quantity} {item}."
                 
    inprogress_orders[session_id] = current_order
    if len(current_order.keys()) == 0:
        fulfillment_text  += "Your order is empty!"
    else:
        order_str = useful_functions.get_str_from_food_dict(current_order)
        fulfillment_text += f"Here is what is left in your orders: {order_str}. Anything else?"


    return JSONResponse(content={
        "fulfillmentText" : fulfillment_text
    })

def add_to_order(parameters: dict, session_id : str):
    food_items = parameters["food-items"]
    quantities = parameters["quantities"]
    
    if len(food_items) != len(quantities):
        fulfillment_text = "Sorry I didn't understand. Can you please specify food items and quantity with each item."
    else:
        new_food_dict = dict(zip(food_items, quantities))

        if session_id in inprogress_orders:
            inprogress_orders[session_id].update(new_food_dict)
        else: 
            inprogress_orders[session_id] = new_food_dict

        
        order_str = useful_functions.get_str_from_food_dict(inprogress_orders[session_id])
        fulfillment_text = f"So far you have: {order_str}. Do you want anything else?"

    return JSONResponse(content={
        "fulfillmentText" : fulfillment_text
    })

def complete_order(parameteres: dict, session_id: str):
    if session_id not in inprogress_orders:
        fulfillment_text = "I'm having a trouble finding your order. Sorry! can you place a new order?"
    else:
        order = inprogress_orders[session_id]
        order_id = save_to_db(order)

        if order_id == -1:
            fulfillment_text= "Sorry, I couldn't process your order due to a backend error. "\
                                "Please place a new order again"
        else:
            order_total = database.get_total_order_price(order_id)
            fulfillment_text = f"Awesome. We have placed your order. "\
                                f"Here is your order id #{order_id}. "\
                                f"Your order total is Rs.{order_total}/- , which can be paid at the time of delivery."
    
        del inprogress_orders[session_id]

    return JSONResponse(content= {
        "fulfillmentText" : fulfillment_text
    })


def save_to_db(order: dict):
    next_order_id = database.get_next_order_id()

    for food_items, quantity in order.items():
        rcode = database.insert_order_item(
            food_items,
            quantity,
            next_order_id
        )

        if rcode == -1:
            return -1
        
    database.insert_order_tracking(next_order_id, "in progress")
        
    return next_order_id
    
def track_order(parameters : dict, session_id : str):
    order_id = int(parameters['number'])
    order_status = database.get_order_status(order_id)

    if order_status:
        fulfillment_text = f"The order status for order id: {order_id} is: {order_status}"
    else:
        fulfillment_text = f"No order found with order id: {order_id}"

    
    return JSONResponse(content={
        "fulfillmentText" : fulfillment_text
    })

def add_more_quantity(parameters : dict, session_id : str):
    
    if session_id not in inprogress_orders:
        return JSONResponse(content={
            "fulfillmentText": "I'm having trouble finding your order. Please place an order first."
        })
    
    food_items = parameters["food-items"]
    quantities = parameters["quantities"] 
    
    if isinstance(food_items, str):
        food_items = [food_items]

    fulfillment_text = ""
    
    for item, quantity in zip(food_items, quantities):
        if item not in inprogress_orders[session_id]:
            fulfillment_text += f"Your order doesn't have {item}. "
        else:
            
            current_qty = int(inprogress_orders[session_id][item])
            new_qty = current_qty + int(quantity)
            inprogress_orders[session_id][item] = str(new_qty)
            fulfillment_text += f"Added {quantity} more {item} to your order. "
    
    
    if len(inprogress_orders[session_id]) > 0:
        order_str = useful_functions.get_str_from_food_dict(inprogress_orders[session_id])
        fulfillment_text += f"Your updated order: {order_str}. Anything Else?"
    
    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


def rating_order(parameters : dict, session_id : str):
    if(session_id in rating_list):
        if "number" in parameters:
            items = list(rating_list[session_id].keys())
            item = items[-(orderlength[session_id])]
            rating_list[session_id][item] = parameters["number"]
            orderlength[session_id] -= 1
            if(orderlength[session_id] == 0):
                for food_items, rating in rating_list[session_id].items():
                    database.insert_rating(food_items,rating)
                del rating_list[session_id]
                fulfillment_text = "Thankyou for your feedback!"
            else:
                item = items[-(orderlength[session_id])]
                fulfillment_text =  f"Please provide the rating between 1-5 for {item}."

        else:
            items = list(rating_list[session_id].keys())
            item = items[-(orderlength[session_id])]
            fulfillment_text =  f"Please provide the rating between 1-5 for {item}."

    else:
        order_id = parameters["number"]
        if(len(order_id) > 1):
            fulfillment_text = "Please provide one order_id at one time."
        else:
            number = int(order_id[0])
            order = database.get_order_items(number)
            if(order == -1):
                fulfillment_text = f"no order with order-id #{number}."
            else:
                rating_list[session_id] = order
                orderlength[session_id] = len(order)
                order_str = useful_functions.get_str_from_food_dict(order)
                fulfillment_text = f"{order_str} This was your order, right?"

        
    
    return JSONResponse(content={
        "fulfillmentText" : fulfillment_text
    })
