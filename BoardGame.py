
from flask import Flask, render_template, request, redirect, url_for
import random
import json
from datetime import datetime, timedelta

app = Flask(__name__)

TOTAL_TILES = 45
PLAYERS = []
player_colors = ['red', 'green', 'yellow', 'blue'][:len(PLAYERS)]
state_file = 'game_state.json'
log_file = 'game_log.txt'

def load_state():
    with open(state_file, 'r') as f:
        return json.load(f)

def save_state(state):
    with open(state_file, 'w') as f:
        json.dump(state, f)

def load_special_tiles():
    with open('special_tiles.json', 'r') as f:
        return json.load(f)

def log_event(message):
    with open(log_file, "a") as f:
        f.write(message + "\n")

@app.route('/')
def home():
    return redirect('/setup')

@app.route('/setup')
def setup():
    return render_template('setup.html')

@app.route('/start', methods=['POST'])
def start():
    num_players = int(request.form['num_players'])
    players = [request.form[f'player{i+1}'] for i in range(num_players)]

    global PLAYERS
    PLAYERS = players
    global player_colors
    player_colors = ['red', 'green', 'yellow', 'blue'][:len(players)]

    state = {
        'positions': [0] * len(players),
        'turn': 0,
        'skips': [0] * len(players),
        'last_card_time': datetime.now().isoformat()
    }
    save_state(state)
    with open(log_file, "w") as f:
        f.write("🎲 Game started!\n")
    return redirect('/board')

@app.route('/board')
def board():
    state = load_state()

    # ⏳ Timed check for drawing a Hall Rush card
    now = datetime.now()
    last_card_time = datetime.fromisoformat(state.get("last_card_time", now.isoformat()))

    #Force pick a Hall Rush card at 120s intervals
    if (now - last_card_time) >= timedelta(seconds=120):
        state["last_card_time"] = now.isoformat()
        save_state(state)
        return redirect('/draw_card')

    # 📝 Load event log
    try:
        with open(log_file, 'r') as f:
            log = f.readlines()
    except FileNotFoundError:
        log = ["No logs yet."]

    return render_template('board.html', state=state, players=PLAYERS, colors=player_colors, log=log)
@app.route('/roll')
def roll():
    state = load_state()
    special_tiles = load_special_tiles()
    current = state['turn']

    if state['skips'][current] > 0:
        state['skips'][current] -= 1
        log_event(f"{PLAYERS[current]} had to skip a turn.")
    else:
        roll = random.randint(1, 6)
        original_position = state['positions'][current]
        new_position = original_position + roll
        if new_position > TOTAL_TILES:
            new_position = TOTAL_TILES

        tile = str(new_position)
        log_message = f"{PLAYERS[current]} rolled a {roll} and moved to tile {new_position}"

        if tile in special_tiles:
            tile_info = special_tiles[tile]
            tile_type = tile_info["type"]

            if tile_type == "wet_floor":
                new_position += tile_info["effect"]
                log_message += f". Slipped on a wet floor and moved to tile {new_position}"
            elif tile_type == "hall_monitor":
                state["skips"][current] += tile_info["skip_turns"]
                log_message += ". Got caught by the hall monitor and must skip a turn"
            elif tile_type == "vending_machine":
                new_position += tile_info["effect"]
                log_message += f". Used a vending machine and ended up on tile {new_position}"
            elif tile_type == "elevator":
                new_position = tile_info["destination"]
                log_message += f". Took the elevator to tile {new_position}"
            elif tile_type == "fire_drill":
                new_position = tile_info["destination"]
                log_message += f". Fire drill! Sent back to tile {new_position}"
            elif tile_type == "shortcut":
                new_position = tile_info["effect"]
                log_message += f". Found a shortcut to tile {new_position}"
            elif tile_type == "energy_drink":
                new_position += tile_info["effect"]
                log_message += f". Drank an energy drink and sprinted to tile {new_position}"
            elif tile_type == "question_tile":
                log_message += ". Landed on a question tile!"
                log_event(log_message)
                return redirect('/draw_card')

        state['positions'][current] = new_position
        log_event(log_message)

        if new_position >= TOTAL_TILES:
            log_event(f"🎉 {PLAYERS[current]} wins the game!")
            return redirect(url_for('winner', name=PLAYERS[current]))

    state['turn'] = (current + 1) % len(PLAYERS)
    save_state(state)
    return redirect('/board')

@app.route('/draw_card')
def draw_card():
    try:
        with open("Hall_Rush_Cards.json", "r") as file:
            cards = json.load(file)
        card = random.choice(cards)
        state = load_state()
        num_players = len(state['positions'])

        # Log card text
        log_event(f"🃏 Hall Rush card drawn: \"{card['text']}\"")

        # Apply card action
        action = card.get("action")
        value = card.get("value", 0)

        if action == "move_leader_back":
            # Find the player furthest ahead
            max_pos = max(state['positions'])
            leader_indices = [i for i, pos in enumerate(state['positions']) if pos == max_pos]
            for i in leader_indices:
                state['positions'][i] = max(0, state['positions'][i] - value)
                log_event(f"{PLAYERS[i]} was in the lead and moved back {value} spaces.")

        elif action == "move_all_forward":
            for i in range(num_players):
                state['positions'][i] = min(TOTAL_TILES, state['positions'][i] + value)
                log_event(f"{PLAYERS[i]} moved forward {value} spaces.")

        elif action == "skip_next_player":
            current_turn = state['turn']
            next_player = (current_turn + 1) % num_players
            state['skips'][next_player] += value
            log_event(f"{PLAYERS[next_player]} will skip {value} turn(s).")

        elif action == "reset_all_positions":
            state['positions'] = [0] * num_players
            log_event("All players returned to the start!")

        save_state(state)
        return render_template('card.html', card=card['text'])

    except Exception as e:
        import traceback
        traceback.print_exc()
        return render_template('card.html', card="Error: Couldn't load or apply card.")
    
@app.route('/winner')
def winner():
    name = request.args.get("name", "Someone")
    return render_template('winner.html', name=name)

@app.route('/reset')
def reset():
    state = {
        'positions': [0] * len(PLAYERS),
        'turn': 0,
        'skips': [0] * len(PLAYERS),
        'last_card_time': datetime.now().isoformat()
    }
    save_state(state)
    with open(log_file, "w") as f:
        f.write("🔄 Game reset.\n")
    return redirect('/setup')

if __name__ == '__main__':
    app.run(debug=True)
