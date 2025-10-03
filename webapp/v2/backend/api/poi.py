#!/usr/bin/env python3
"""
POI API endpoints for AudioMoth Spectrogram Viewer
Handles Points of Interest browsing and deep linking
"""

from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from database import execute_raw_query

poi_bp = Blueprint('poi', __name__, url_prefix='/poi')


@poi_bp.route('/test')
def test_route():
    """Test route to verify POI blueprint is working"""
    return "POI Blueprint is working! Route accessed successfully."


def format_time_seconds(seconds):
    """Format seconds into HH:MM:SS format"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@poi_bp.route('/')
def poi_page():
    """Main POI browsing page"""
    try:
        # Get all research goals with their POIs
        goals_query = """
        SELECT 
            id, title, description, created_at
        FROM research_goals 
        ORDER BY created_at DESC
        """
        goals_data = execute_raw_query(goals_query)
        print(f"Debug: Found {len(goals_data)} goals in database")
        
        goals = []
        for goal_row in goals_data:
            print(f"Debug: Processing goal row: {goal_row}")
            
            # Parse created_at safely
            created_at = None
            if len(goal_row) > 3 and goal_row[3]:
                try:
                    dt_str = str(goal_row[3])
                    if 'T' in dt_str:
                        created_at = datetime.fromisoformat(dt_str.replace('T', ' '))
                    else:
                        created_at = datetime.fromisoformat(dt_str)
                except Exception as e:
                    print(f"Debug: Error parsing datetime '{goal_row[3]}': {e}")
                    created_at = None
                
            goal = {
                'id': goal_row[0],
                'title': goal_row[1],
                'description': goal_row[2] if len(goal_row) > 2 else '',
                'created_at': created_at,
                'pois': []
            }
            
            # Get POIs for this goal
            try:
                pois_query = """
                SELECT 
                    p.id, p.label, p.notes, p.confidence, p.anchor_index_name, p.created_at
                FROM points_of_interest p
                WHERE p.goal_id = ?
                ORDER BY p.created_at DESC
                """
                pois_data = execute_raw_query(pois_query, (goal['id'],))
                
                for poi_row in pois_data:
                    poi = {
                        'id': poi_row[0],
                        'label': poi_row[1],
                        'notes': poi_row[2] if poi_row[2] else '',
                        'confidence': poi_row[3] if poi_row[3] else 0.0,
                        'anchor_index_name': poi_row[4] if poi_row[4] else '',
                        'spans': []
                    }
                    
                    # Get spans for this POI
                    try:
                        spans_query = """
                        SELECT 
                            ps.id, ps.start_time_sec, ps.end_time_sec, ps.chunk_start, ps.chunk_end,
                            ps.config_name, ps.processing_type, ps.created_at,
                            af.id, af.filename, af.filepath, af.recording_datetime
                        FROM poi_spans ps
                        JOIN audio_files af ON ps.file_id = af.id
                        WHERE ps.poi_id = ?
                        ORDER BY af.recording_datetime, ps.start_time_sec
                        """
                        spans_data = execute_raw_query(spans_query, (poi['id'],))
                        
                        for span_row in spans_data:
                            span = {
                                'id': span_row[0],
                                'file_id': span_row[8],  # af.id (file_id from JOIN)
                                'file_name': span_row[9],  # af.filename  
                                'start_time_sec': span_row[1],
                                'end_time_sec': span_row[2],
                                'start_time_formatted': format_time_seconds(span_row[1]),
                                'end_time_formatted': format_time_seconds(span_row[2]),
                            }
                            poi['spans'].append(span)
                    except Exception as e:
                        print(f"Debug: Error loading spans for POI {poi['id']}: {e}")
                    
                    goal['pois'].append(poi)
                    
            except Exception as e:
                print(f"Debug: Error loading POIs for goal {goal['id']}: {e}")
            
            goals.append(goal)
        
        print(f"Debug: Returning {len(goals)} goals to template")
        return render_template('poi.html', goals=goals)
        
    except Exception as e:
        print(f"Error loading POI page: {e}")
        import traceback
        traceback.print_exc()
        return render_template('poi.html', goals=[])


@poi_bp.route('/api/goals')
def api_goals():
    """API endpoint for goals data"""
    try:
        goals_query = """
        SELECT 
            id, title, description, created_at,
            (SELECT COUNT(*) FROM points_of_interest WHERE goal_id = research_goals.id) as poi_count
        FROM research_goals 
        ORDER BY created_at DESC
        """
        goals_data = execute_raw_query(goals_query)
        
        goals = []
        for row in goals_data:
            goal = {
                'id': row[0],  # id
                'title': row[1],  # title
                'description': row[2],  # description
                'created_at': row[3],  # created_at
                'poi_count': row[4]  # poi_count
            }
            goals.append(goal)
        
        return jsonify(goals)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@poi_bp.route('/api/goal/<int:goal_id>/pois')
def api_goal_pois(goal_id):
    """API endpoint for POIs of a specific goal"""
    try:
        pois_query = """
        SELECT 
            p.id, p.label, p.notes, p.confidence, p.anchor_index_name, p.created_at,
            (SELECT COUNT(*) FROM poi_spans WHERE poi_id = p.id) as span_count
        FROM points_of_interest p
        WHERE p.goal_id = ?
        ORDER BY p.created_at DESC
        """
        pois_data = execute_raw_query(pois_query, (goal_id,))
        
        pois = []
        for row in pois_data:
            poi = {
                'id': row[0],  # id
                'label': row[1],  # label
                'notes': row[2],  # notes
                'confidence': row[3],  # confidence
                'anchor_index_name': row[4],  # anchor_index_name
                'created_at': row[5],  # created_at
                'span_count': row[6]  # span_count
            }
            pois.append(poi)
        
        return jsonify(pois)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@poi_bp.route('/api/poi/<int:poi_id>/spans')
def api_poi_spans(poi_id):
    """API endpoint for spans of a specific POI"""
    try:
        spans_query = """
        SELECT 
            ps.id, ps.start_time_sec, ps.end_time_sec, ps.chunk_start, ps.chunk_end,
            ps.config_name, ps.processing_type, ps.created_at,
            af.id as file_id, af.filename, af.filepath, af.recording_datetime
        FROM poi_spans ps
        JOIN audio_files af ON ps.file_id = af.id
        WHERE ps.poi_id = ?
        ORDER BY af.recording_datetime, ps.start_time_sec
        """
        spans_data = execute_raw_query(spans_query, (poi_id,))
        
        spans = []
        for row in spans_data:
            span = {
                'id': row[0],  # ps.id
                'file_id': row[8],  # af.id
                'file_name': row[9],  # af.filename
                'file_path': row[10],  # af.filepath
                'start_time_sec': row[1],  # ps.start_time_sec
                'end_time_sec': row[2],  # ps.end_time_sec
                'start_time_formatted': format_time_seconds(row[1]),  # ps.start_time_sec
                'end_time_formatted': format_time_seconds(row[2]),  # ps.end_time_sec
                'chunk_start': row[3],  # ps.chunk_start
                'chunk_end': row[4],  # ps.chunk_end
                'config_name': row[5],  # ps.config_name
                'processing_type': row[6],  # ps.processing_type
                'created_at': row[7],  # ps.created_at
                'datetime_recorded': row[11]  # af.recording_datetime
            }
            spans.append(span)
        
        return jsonify(spans)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500