# AudioMoth Web Interface v2

## Clean rebuild based on lessons learned from v1

### Key Improvements
- Modular architecture with separated concerns
- Clean CSS/JS separation 
- Modern ES6+ JavaScript modules
- Better error handling and user feedback
- Responsive design
- Improved performance

### Structure
```
v2/
├── static/
│   ├── css/          # Separated stylesheets
│   └── js/           # Modular JavaScript
├── templates/        # Clean HTML templates
├── docs/            # Architecture and specs
└── app.py           # Clean Flask application
```

### Development Notes
- Start with core functionality first
- Add features incrementally
- Test thoroughly at each step
- Document as you go