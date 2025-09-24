"""
Chess Multiplayer Server - Render.com Deployment Version
Minimal server with only networking components
"""
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid
import time
import os
from typing import Dict, List, Optional

# Simple network game state for server
class ServerGameState:
    def __init__(self, game_id: str = "", player_white: str = "", player_black: str = ""):
        self.game_id = game_id
        self.player_white = player_white
        self.player_black = player_black
        self.game_status = "waiting"
        self.turn_step = 0  # 0-white turn, 2-black turn
        self.move_count = 0
        self.winner = ""
        self.game_over = False
        
        # Basic piece tracking for move validation
        self.white_pieces = ['rook', 'rook', 'knight', 'knight', 'bishop', 'bishop', 'king', 'queen',
                            'bishop', 'bishop', 'knight', 'knight', 'rook', 'rook'] + ['pawn'] * 16
        self.black_pieces = ['rook', 'rook', 'knight', 'knight', 'bishop', 'bishop', 'queen', 'king',
                            'bishop', 'bishop', 'knight', 'knight', 'rook', 'rook'] + ['pawn'] * 16
        self.white_locations = [(0, 0), (1, 0), (4, 1), (5, 1), (4, 0), (5, 0), (8, 0), (7, 0),
                               (10, 0), (11, 0), (10, 1), (11, 1), (14, 0), (15, 0)] + \
                              [(i, j) for i in range(16) for j in [1, 2] if (i, j) not in [(4, 1), (5, 1), (10, 1), (11, 1)]][:16]
        self.black_locations = [(0, 9), (1, 9), (4, 8), (5, 8), (4, 9), (5, 9), (7, 9), (8, 9),
                               (10, 9), (11, 9), (10, 8), (11, 8), (14, 9), (15, 9)] + \
                              [(i, j) for i in range(16) for j in [8, 7] if (i, j) not in [(4, 8), (5, 8), (10, 8), (11, 8)]][:16]
    
    def to_dict(self):
        return {
            'game_id': self.game_id,
            'player_white': self.player_white,
            'player_black': self.player_black,
            'game_status': self.game_status,
            'turn_step': self.turn_step,
            'move_count': self.move_count,
            'winner': self.winner,
            'game_over': self.game_over,
            'white_pieces': self.white_pieces,
            'black_pieces': self.black_pieces,
            'white_locations': self.white_locations,
            'black_locations': self.black_locations
        }
    
    def get_current_player(self):
        return 'white' if self.turn_step < 2 else 'black'
    
    def is_valid_move_basic(self, from_pos, to_pos, player):
        """Basic move validation"""
        # Simple validation - just check if positions are on board
        if not (0 <= from_pos[0] < 16 and 0 <= from_pos[1] < 10):
            return False
        if not (0 <= to_pos[0] < 16 and 0 <= to_pos[1] < 10):
            return False
        return True

# Server configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'chess-server-secret-key-change-in-production')
DEBUG_MODE = os.getenv('DEBUG', 'False').lower() == 'true'

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=30, ping_interval=5)

# Game storage
active_games: Dict[str, ServerGameState] = {}
player_sessions: Dict[str, str] = {}
player_games: Dict[str, str] = {}
waiting_players: List[str] = []

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connection_response', {'status': 'connected', 'session_id': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    session_id = request.sid
    print(f"Client disconnected: {session_id}")
    
    if session_id in player_sessions:
        player_name = player_sessions[session_id]
        if player_name in waiting_players:
            waiting_players.remove(player_name)
        
        if player_name in player_games:
            game_id = player_games[player_name]
            if game_id in active_games:
                game = active_games[game_id]
                game.game_status = 'paused'
                socketio.emit('player_disconnected', 
                            {'player': player_name, 'game_status': 'paused'}, 
                            room=game_id)
        
        del player_sessions[session_id]
        if player_name in player_games:
            del player_games[player_name]

@socketio.on('register_player')
def handle_register_player(data):
    player_name = data.get('name', '').strip()[:20]  # Sanitize and limit length
    if not player_name:
        emit('error', {'message': 'Invalid player name'})
        return
    
    session_id = request.sid
    player_sessions[session_id] = player_name
    
    print(f"Player registered: {player_name}")
    emit('registration_success', {'player_name': player_name})

@socketio.on('find_game')
def handle_find_game():
    session_id = request.sid
    if session_id not in player_sessions:
        emit('error', {'message': 'Player not registered'})
        return
    
    player_name = player_sessions[session_id]
    
    if player_name in player_games:
        game_id = player_games[player_name]
        if game_id in active_games:
            emit('error', {'message': 'Already in a game'})
            return
    
    # Try to match with waiting player
    if waiting_players and waiting_players[0] != player_name:
        opponent = waiting_players.pop(0)
        
        # Create new game
        game_id = str(uuid.uuid4())
        game = ServerGameState(
            game_id=game_id,
            player_white=player_name,
            player_black=opponent
        )
        game.game_status = 'active'
        
        active_games[game_id] = game
        player_games[player_name] = game_id
        player_games[opponent] = game_id
        
        # Join both players to room
        join_room(game_id)
        opponent_session = None
        for sid, pname in player_sessions.items():
            if pname == opponent:
                opponent_session = sid
                break
        
        if opponent_session:
            socketio.server.enter_room(opponent_session, game_id)
        
        # Notify both players
        game_data = game.to_dict()
        socketio.emit('game_started', game_data, room=game_id)
        
        print(f"Game started: {game_id} ({player_name} vs {opponent})")
        
    else:
        if player_name not in waiting_players:
            waiting_players.append(player_name)
        emit('waiting_for_opponent', {'message': 'Waiting for an opponent...'})
        print(f"Player {player_name} waiting for opponent")

@socketio.on('make_move')
def handle_make_move(data):
    session_id = request.sid
    if session_id not in player_sessions:
        emit('error', {'message': 'Player not registered'})
        return
    
    player_name = player_sessions[session_id]
    game_id = data.get('game_id')
    
    if game_id not in active_games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = active_games[game_id]
    
    # Basic validation
    current_player = game.get_current_player()
    if (current_player == 'white' and player_name != game.player_white) or \
       (current_player == 'black' and player_name != game.player_black):
        emit('error', {'message': 'Not your turn'})
        return
    
    from_pos = tuple(data['from_pos'])
    to_pos = tuple(data['to_pos'])
    
    if game.is_valid_move_basic(from_pos, to_pos, player_name):
        # Update game state
        game.move_count += 1
        game.turn_step = (game.turn_step + 2) % 4  # Switch turns
        
        # Broadcast move
        move_data = {
            'type': 'move_made',
            'game_state': game.to_dict(),
            'move': data
        }
        socketio.emit('move_update', move_data, room=game_id)
        print(f"Move in game {game_id}: {from_pos} -> {to_pos}")
    else:
        emit('error', {'message': 'Invalid move'})

@socketio.on('forfeit_game')
def handle_forfeit(data):
    session_id = request.sid
    if session_id not in player_sessions:
        emit('error', {'message': 'Player not registered'})
        return
    
    player_name = player_sessions[session_id]
    
    if player_name not in player_games:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_id = player_games[player_name]
    if game_id not in active_games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = active_games[game_id]
    
    # Determine winner
    if player_name == game.player_white:
        game.winner = game.player_black
    else:
        game.winner = game.player_white
    
    game.game_over = True
    game.game_status = 'finished'
    
    # Notify players
    socketio.emit('game_ended', {
        'winner': game.winner,
        'reason': 'forfeit',
        'forfeiter': player_name
    }, room=game_id)
    
    # Cleanup
    cleanup_game(game_id)

def cleanup_game(game_id: str):
    if game_id in active_games:
        game = active_games[game_id]
        
        if game.player_white in player_games:
            del player_games[game.player_white]
        if game.player_black in player_games:
            del player_games[game.player_black]
        
        del active_games[game_id]

@app.route('/')
def home():
    return f"""
    <h1>Chess Multiplayer Server</h1>
    <p>Server is running!</p>
    <p>Active games: {len(active_games)}</p>
    <p>Connected players: {len(player_sessions)}</p>
    <p>Waiting players: {len(waiting_players)}</p>
    """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Chess Server on port {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=DEBUG_MODE)