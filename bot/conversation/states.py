"""FSM states and the legal transitions between them."""


class State:
    IDLE = "IDLE"
    MAIN_MENU = "MAIN_MENU"

    ASK_ORIGIN = "ASK_ORIGIN"
    PICK_ORIGIN = "PICK_ORIGIN"
    ASK_DESTINATION = "ASK_DESTINATION"
    PICK_DESTINATION = "PICK_DESTINATION"
    ASK_DATE = "ASK_DATE"
    ASK_TRIP = "ASK_TRIP"
    ASK_SEATS = "ASK_SEATS"
    ASK_NAME = "ASK_NAME"
    CONFIRM = "CONFIRM"

    ASK_PNR = "ASK_PNR"
    CONFIRM_CANCEL = "CONFIRM_CANCEL"

    BROWSE_STOPS = "BROWSE_STOPS"


# Flows share the origin/destination states; this flag says what to do once
# both stops are known, so a fare enquiry doesn't duplicate four states.
class Flow:
    BOOK = "BOOK"
    FARE = "FARE"


ALL_STATES = {
    value for name, value in vars(State).items() if not name.startswith("_")
}

# Asserted in tests: every handler must map to a known state.
ALLOWED_TRANSITIONS = {
    State.IDLE: {State.MAIN_MENU},
    State.MAIN_MENU: {
        State.ASK_ORIGIN,
        State.ASK_PNR,
        State.BROWSE_STOPS,
        State.MAIN_MENU,
    },
    State.ASK_ORIGIN: {State.PICK_ORIGIN, State.ASK_DESTINATION, State.ASK_ORIGIN, State.BROWSE_STOPS},
    State.PICK_ORIGIN: {State.ASK_DESTINATION, State.PICK_ORIGIN},
    State.ASK_DESTINATION: {
        State.PICK_DESTINATION,
        State.ASK_DATE,
        State.ASK_DESTINATION,
        State.MAIN_MENU,
        State.BROWSE_STOPS,
    },
    State.PICK_DESTINATION: {State.ASK_DATE, State.PICK_DESTINATION, State.MAIN_MENU},
    State.ASK_DATE: {State.ASK_TRIP, State.ASK_DATE, State.MAIN_MENU},
    State.ASK_TRIP: {State.ASK_SEATS, State.ASK_TRIP, State.MAIN_MENU},
    State.ASK_SEATS: {State.ASK_NAME, State.CONFIRM, State.ASK_SEATS},
    State.ASK_NAME: {State.CONFIRM, State.ASK_NAME},
    State.CONFIRM: {State.MAIN_MENU, State.CONFIRM},
    State.ASK_PNR: {State.MAIN_MENU, State.CONFIRM_CANCEL, State.ASK_PNR},
    State.CONFIRM_CANCEL: {State.MAIN_MENU, State.CONFIRM_CANCEL},
    State.BROWSE_STOPS: {State.BROWSE_STOPS, State.MAIN_MENU, State.ASK_ORIGIN},
}
