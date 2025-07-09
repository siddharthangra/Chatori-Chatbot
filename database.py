import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

def get_connection():
    return mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    port=int(os.getenv("DB_PORT", 3306))
)


def get_order_status(order_id : int):
    cnx = get_connection()
    cursor = cnx.cursor()

    query = ("SELECT status FROM order_tracking WHERE order_id = %s")
    cursor.execute(query,(order_id,))
    result = cursor.fetchone()

    cursor.close()
    cnx.close()
    if result is not None:
        return result[0]
    else:
        return None
    
def get_next_order_id():
    cnx = get_connection()
    cursor = cnx.cursor()

    query = "SELECT MAX(order_id) FROM orders"
    cursor.execute(query)

    result = cursor.fetchone()

    cursor.close()
    cnx.close()
    print("DEBUG - get_next_order_id result:", result) #debugginhg

    if result[0] is None:
        return 1    
    else:
        return result[0] + 1

def insert_order_item(food_item, quantity, order_id):
    try:
        cnx = get_connection()
        cursor = cnx.cursor()
        cursor.callproc('insert_order_item', (food_item, quantity, order_id))
        cnx.commit()

        cursor.close()
        cnx.close()
        print("Order item inserted successfully!")

        return 1

    except mysql.connector.Error as err:
        print(f"Error inserting order item: {err}")
        cnx.rollback()

        return -1

    except Exception as e:
        print(f"An error occurred: {e}")
        cnx.rollback()

        return -1


def get_price_of_item(item):
    try:
        cnx = get_connection()
        cursor = cnx.cursor()
        query = "SELECT price FROM food_items WHERE name = %s"
        cursor.execute(query, (item,))
        
        result = cursor.fetchone()
        cursor.close()
        cnx.close()
        
        if result:
            return result[0]
        else:
            return -1  # Item not found
            
    except Exception as e:
        print(f"Error getting price for item {item}: {e}")
        return -1


def insert_order_tracking(order_id, status):
    cnx = get_connection()
    cursor = cnx.cursor()
    insert_query = "INSERT INTO order_tracking (order_id, status) VALUES (%s,%s)"
    cursor.execute(insert_query,(order_id,status))

    cnx.commit()

    cursor.close()
    cnx.close()

def get_order_items(order_id : int):
    cnx = get_connection()
    cursor = cnx.cursor()
    query =  ("""
        select food_items.name, orders.quantity 
        from food_items 
        join orders on orders.item_id = food_items.item_id
        where order_id = %s;
        """
    )
    cursor.execute(query,(order_id,))
    result = cursor.fetchall()
    cursor.close()
    cnx.close()

    if not result:
        return -1
    else:
        return {item_name: quantity for item_name, quantity in result}

def get_current_rating(food_item):
    cnx = get_connection()
    cursor = cnx.cursor()
    query = ("""
        Select rating, rating_count  from food_rating where food_item  = %s
             """)
    cursor.execute(query, (food_item,))
    result = cursor.fetchone()
    cursor.close()

    rating, count = result
    total_rating = rating * count
    return total_rating, count

def insert_rating(food_item, rating):
    total_rating, count = get_current_rating(food_item)
    new_count = count + 1
    avg_rating = round(((total_rating + rating[0])/new_count),1)
    cnx = get_connection()
    cursor = cnx.cursor()
    query = ("""
        Update food_rating
        set rating = %s , rating_count = %s
        where food_item = %s
             """)
    
    cursor.execute(query,(avg_rating,new_count,food_item))
    cnx.commit()
    cursor.close()
    

def get_all_food_items():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
    select fr.food_item, fr.rating , fr.rating_count, fi.price
    from food_rating fr
    join food_items fi
    on fr.food_item = fi.name
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    food_list = []
    for row in rows:
        food_list.append({
            "name": row["food_item"],
            "price": row["price"],
            "avg_rating": row["rating"],
            "rating_count": row["rating_count"]
        })

    cursor.close()
    connection.close()
    return food_list



    

