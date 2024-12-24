from django.shortcuts import render

# Create your views here.
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from .forms import BookingForm 
from twilio.rest import Client
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from bot.models import Booking
from django.http import HttpResponse
from django.utils.timezone import now
from .models import Booking
# @csrf_exempt  # Disable CSRF for this view

# def twilio_webhook(request):

#     if request.method == 'POST':

#         # Get the incoming message and sender's WhatsApp number

#         incoming_msg = request.POST.get('Body', '').strip().lower()

        


#         # Create a Twilio response object

#         response = MessagingResponse()


#         # Check the incoming message and respond accordingly

#         if incoming_msg == 'hello':

#             response.message("Hello dear, welcome to AITS Indore!")

#         elif incoming_msg == 'booking our ticket':

#             response.message("To book your ticket, please visit: http://127.0.0.1:8000/bot/register")

#         elif incoming_msg == 'book your ticket':

#             # Fetch the WhatsApp number from the request

#               # Clean the number


#             # Check if the user has an entry in the Booking table

#             try:

#                 booking = Booking.objects.get(whatsapp_number=whatsapp_number)

#                 response.message(f"Your ticket is confirmed! Booking ID: {booking.id}")

#             except Booking.DoesNotExist:

#                 response.message("No booking found for this number. Please make a booking first.")


#         else:

#             response.message("Sorry, I didn't understand that. Please type 'hello' or 'booking our ticket'.")


#         return JsonResponse(str(response), safe=False)  # Return the Twilio response


#     return JsonResponse({'error': 'Invalid request'}, status=400)
@csrf_exempt
def whatsapp_bot(request):
    if request.method == "POST":
        from_number = request.POST.get('From', '')
        incoming_message = request.POST.get('Body', '').strip().lower()
        greetings = ['hello', 'hii', 'hi', 'hy', 'hye']
        # Start of conversation
        response = MessagingResponse()

        if incoming_message in greetings:
            # Greeting message and options
            response.message(" 😃😃 Hello! Welcome to iBus Services 🚌. Visit our website to get started:\n  link is below 🔗 /n http://127.0.0.1:8000/bot/register")
            response.message(" Here are your options:\n1. Book my Ticket 🎟️ \n2. show my ticket 🎟️ \n3. Recently visited routes 📍")
        
        elif "book my ticket" in incoming_message or "1" in incoming_message: 
            # Redirect to iBus booking page (this would be your website URL)
            
            response.message("To book your ticket, please visit: 😃 \n http://127.0.0.1:8000/bot/booking")
        
        elif "show my ticket" in incoming_message or "2" in incoming_message:
            # Provide information about nearby stations (to be defined on your website)
            
            
            try:
                whatsapp_number = from_number.replace('whatsapp:', '')
                bookings = Booking.objects.filter(whatsapp_number=whatsapp_number).order_by('-created_at')
                print(bookings)
                booking=bookings.first()
                

                # Fetch user details

                username = booking.user.username

                route = booking.route

                ticket_count = booking.ticket_count

                created_at = booking.created_at.strftime("%Y-%m-%d %H:%M:%S")  # Format date and time


                # Create a detailed response message

                response.message(

                    f"Thank you for visiting AITS Indore 😃, {username}!\n"

                    f"Your ticket 🎟️ is confirmed!\n"

                    f"Booking ID: {booking.id}\n"

                    f"Route 📍: {route.source} to {route.destination}\n"

                    f"Ticket Count 🎟️: {ticket_count}\n"

                    f"Date and Time 📅: {created_at}\n"

                    f"Total Price 💸: {booking.total_price:.2f} INR"

                )

            except Booking.DoesNotExist:

                response.message("No booking found for this number. Please make a booking first.")
        elif "recently visited routes" in incoming_message or "3" in incoming_message:
            try:
                whatsapp_number = from_number.replace('whatsapp:', '')
                bookings = Booking.objects.filter(whatsapp_number=whatsapp_number).order_by('-created_at')
                print(bookings)
                booking=bookings.first()
                second_booking = bookings[1]  # Second element (index starts at 0)
                third_booking = bookings[2]
                route1 = booking.route
                route2=second_booking.route
                route3=third_booking.route
                response.message(

                    f"Route 📍: {route1.source} to {route1.destination}\n"
                    f"Route 📍: {route2.source} to {route2.destination}\n"
                    f"Route 📍: {route3.source} to {route3.destination}\n"

                )
            except Booking.DoesNotExist:

                response.message("No booking found for this number. Please make a booking first.")
            
        else:
            
            # Handle invalid input
            response.message("Sorry, I didn't understand that. Please choose one of the options: 'Book Your Ticket', or 'More Options'.")

        return HttpResponse(str(response), content_type="application/xml")
    else:
        return HttpResponse("Invalid request method", status=405)

 # Assuming you've created a form for booking
@csrf_exempt
# def booking_view(request):
    # if request.method == 'POST':
    #     form = BookingForm(request.POST)
    #     if form.is_valid():
    #         # Process the form (this would save data to the database, like user details, source, and destination)
    #         source = form.cleaned_data['source']
    #         destination = form.cleaned_data['destination']

    #         # After registration, user will proceed to payment page
    #         return HttpResponse(f"Booking details saved! You are traveling from {source} to {destination}. Proceed to payment.")
    #     else:
    #         return HttpResponse("Invalid form data", status=400)
    
    # # If GET request, show the booking form
    # else:
    #     form = BookingForm()
    #     return render(request, 'bot/booking.html')
    # if request.method == 'POST':

    #     form = BookingForm(request.POST)

    #     if form.is_valid():

    #         booking = form.save(commit=False)

    #         booking.user = request.user  # Set the user to the currently logged-in user

    #         booking.save()

    #         return redirect('payment_view')  # Redirect to the payment view

    # else:

    #     form = BookingForm()

    

    # return render(request, 'bot/booking.html')
    # views.py

# @csrf_exempt
# def booking_view(request):
#     if request.method == 'POST':
#         form = BookingForm(request.POST)
#         if form.is_valid():
#             print("form valid hai")
#             booking = form.save(commit=False)
#             booking.user = request.user  # Set the user to the currently logged-in user
#             booking.save()  # This will trigger the save method in the Booking model
#             # return redirect('payment_view')  
#             # # Redirect to the payment view
#             return render(request, 'bot/payment.html', {'form': form})
#     else:
#         form = BookingForm()
    
#     return render(request, 'bot/booking.html', {'form': form})
@csrf_exempt

def booking_view(request):

    print(request)

    if request.method == 'POST':

        form = BookingForm(request.POST)

        print(form)

        if form.is_valid():

            print("valid")

            booking = form.save(commit=False)

            booking.user = request.user  # Set the user to the currently logged-in user

            booking.save()  # Save the booking to the database


            # Redirect to the payment view with the booking ID

            return redirect('payment_view', booking_id=booking.id)


    else:

        form = BookingForm()


    return render(request, 'bot/booking.html', {'form': form})
from django.shortcuts import render

def index(request):
    return render(request, 'bot/index.html')  # Adjust the template name as needed
    
    # if request.method == "POST":
    #     # Extract incoming message
    #     incoming_message = request.POST.get('Body', '')

    #     # Create a Twilio MessagingResponse object
    #     response = MessagingResponse()
    #     response.message(f"Hi there! You said: {incoming_message}")

    #     # Return the response in XML format
    #     return HttpResponse(str(response), content_type="application/xml")
    # else:
    #     return HttpResponse("Invalid request method", status=405)

# def payment_view(request):
#     # Fetch the logged-in user's username
#     print(request)
#     username = request.user.username

#     # Fetch the latest booking details for the logged-in user
#     try:
#         booking = Booking.objects.filter(user=request.user).latest('created_at')  # Assuming 'created_at' field exists
#         source = booking.source
#         destination = booking.destination
#         booking_id = booking.iddef payment_view(request):
    # Fetch the logged-in user's username
    username = request.user.username
    
    # Fetch the latest booking details for the logged-in user
    try:
        booking = Booking.objects.filter(user=request.user).latest('created_at')  # Assuming 'created_at' field exists
        source = booking.route.source  # Accessing the source from the related Route
        destination = booking.route.destination  # Accessing the destination from the related Route
        booking_id = booking.id
        print(booking)
    except Booking.DoesNotExist:
        return HttpResponse("No booking found. Please book a ticket first.")

    # Generate the ticket with the current date and time
    current_time = now().strftime("%Y-%m-%d %H:%M:%S")
    ticket = (
        f"Your Ticket:\n"
        f"Username: {username}\n"
        f"Source: {source}\n"
        f"Destination: {destination}\n"
        f"Booking ID: {booking_id}\n"
        f"Date and Time: {current_time}"
    )

    # Send the ticket to WhatsApp via Twilio
    send_ticket_via_whatsapp(ticket)

    return HttpResponse(f"Payment complete! Your ticket:\n\n{ticket}")
#     except Booking.DoesNotExist:
#         return HttpResponse("No booking found. Please book a ticket first.")

#     # Generate the ticket with the current date and time
#     current_time = now().strftime("%Y-%m-%d %H:%M:%S")
#     ticket = (
#         f"Your Ticket:\n"
#         f"Username: {username}\n"
#         f"Source: {source}\n"
#         f"Destination: {destination}\n"
#         f"Booking ID: {booking_id}\n"
#         f"Date and Time: {current_time}"
#     )

#     # Send the ticket to WhatsApp via Twilio
#     send_ticket_via_whatsapp(ticket)

#     return HttpResponse(f"Payment complete! Your ticket:\n\n{ticket}")
@csrf_exempt  
@login_required


def payment_view(request, booking_id):
    # Fetch the logged-in user's username
    username = request.user.username

    # Fetch the booking details for the logged-in user using the booking_id
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)  # Ensure the booking belongs to the user
        source = booking.route.source  # Accessing the source from the related Route
        destination = booking.route.destination
        # whatsapp_number = request.user.whatsapp_number
        whatsapp_number = booking.whatsapp_number  # Accessing the destination from the related Route
        print(booking)
    except Booking.DoesNotExist:
        return HttpResponse("No booking found. Please book a ticket first.")

    # Generate the ticket with the current date and time
    current_time = now().strftime("%Y-%m-%d %H:%M:%S")
    ticket = (
        f"Your Ticket:\n"
        f"Username: {username}\n"
        f"Source: {source}\n"
        f"Destination: {destination}\n"
        f"Booking ID: {booking_id}\n"
        f"Date and Time: {current_time}"
    )
    print(whatsapp_number)
    # Send the ticket to WhatsApp via Twilio
    

    return render(request, 'bot/payment.html',locals())
    # return HttpResponse(f"Payment complete! Your ticket:\n\n{ticket}")

def send_ticket_via_whatsapp(ticket,user_whatsapp_number):
    # Use your Twilio Account SID and Auth Token
    # 
    client = Client(account_sid, auth_token)

    # Send the ticket to the user (replace with actual user WhatsApp number)
    message = client.messages.create(
        body=ticket,
        from_='whatsapp:+12185035494',  # Twilio sandbox number
        to=f'whatsapp:{user_whatsapp_number}', # User's WhatsApp number
    )

@csrf_exempt
def register(request):
    # if request.method == 'POST':
    #     form = UserCreationForm(request.POST)
    #     if form.is_valid():
    #         form.save()
    #         return redirect('login')  # Redirect to login page after successful registration
    # else:
    #     form = UserCreationForm()

    # return render(request, 'bot/register.html')
    if request.method== 'POST':
       first_name=request.POST.get("first_name")
       last_name=request.POST.get("last_name")
       username=request.POST.get("username")
       password=request.POST.get("password")
    #    whatsapp_number=request.POST.get("whatsapp")
       user=User.objects.filter(username=username)
       if user.exists():
          messages.info(request,"username already taken ")
          return render(request, 'bot/register.html')
       user = User.objects.create(

    first_name=first_name,

    last_name=last_name,

    username=username,

    # whatsapp_number=whatsapp_number,  # Ensure this matches the field name in your model

)
       user.set_password(password)
       user.save()
       messages.info(request,"successfully user created")
       return render(request, 'bot/login.html')
       
    return render(request, 'bot/register.html')

@csrf_exempt
def login_view(request):
    # if request.method == 'POST':
    #     form = AuthenticationForm(data=request.POST)
    #     if form.is_valid():
    #         user = form.get_user()
    #         login(request, user)
    #         return redirect('booking')  # After login, redirect to booking page
    # else:
    #     form = AuthenticationForm()
    print("POST method ke uper")
    if request.method == 'POST':
        print("POST method ke ander")
        username=request.POST.get('username')
        password=request.POST.get('login_password')
        print(username,password)
        if not User.objects.filter(username=username).exists():
            messages.error(request,"invalid username")
            return render(request, 'bot/login.html')
        user=authenticate(username=username,password=password)
        print("--------------------",user)
        if user is None:
            messages.error(request,"invalid password")
            return render(request, 'bot/login.html')

        else:
            login(request,user)
            return render(request, 'bot/index.html')

    return render(request, 'bot/login.html')
