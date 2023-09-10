# GitHub Stats Dashboard

Visualize your GitHub activity, language distribution, and repository statistics.

## Features

- Profile overview (followers, repos, bio)
- Repository stats (stars, forks, size)
- Language distribution across repos
- Recent activity summary
- Charts: language pie chart, top repos bar chart, daily activity
- JSON export

## Usage

```bash
pip install -r requirements.txt

# Basic stats
python main.py Bisman-Singh

# With charts
python main.py Bisman-Singh --charts

# With token for higher rate limits
python main.py Bisman-Singh --token YOUR_TOKEN --charts

# Export to JSON
python main.py Bisman-Singh --export-json stats.json
```
