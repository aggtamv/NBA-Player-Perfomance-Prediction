# NBA Prophit

NBA Prophit is an interactive web application for visualizing NBA player shooting statistics and predicting player plus-minus performance using deep learning. The app scrapes data from Basketball Reference, visualizes statistics with Plotly, and predicts player plus-minus based on recent game data using a simple RNN model deployed via Hugging Face API.

---

## Features

- Interactive visualization of raw and adjusted shooting averages across years.
- Plus-minus prediction for NBA players using a PyTorch RNN model.
- Data scraping from Basketball Reference with Pandas.
- Clean and responsive UI built with Flask and Dash.

---

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/nba-prophit.git
    cd nba-prophit
    ```

2. (Optional) Create and activate a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

3. Install required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4. Run the Flask app:
    ```bash
    flask run
    ```

5. Open your browser and go to [http://localhost:5000/stats](http://localhost:5000/stats) to access the shooting stats dashboard.

---

## Usage

- Navigate to `/stats` to explore shooting statistics visualized with interactive Plotly graphs.
- Use the plus-minus prediction feature by entering a player’s last 10 game stats (integrated via the Hugging Face API).
- The app dynamically updates plots and predictions based on your input.

---

## Model Details

- The plus-minus prediction model is a simple Recurrent Neural Network (RNN) implemented in PyTorch.
- It uses sequential data from the last 10 games of a player to forecast the plus-minus metric.
- The model is trained on historical NBA data and deployed on Hugging Face for easy API access.
- Predictions are fetched in real-time from the Hugging Face API within the Flask app.

---

## Future Work

- Improve the RNN model by experimenting with LSTM or Transformer architectures for better accuracy.
- Add more player statistics and advanced analytics.
- Implement user authentication for personalized experience.
- Expand data scraping to include live game updates.
- Optimize front-end UI for mobile responsiveness.

---

## Acknowledgements

- [Basketball Reference](https://www.basketball-reference.com/) for comprehensive NBA statistics.
- [Plotly](https://plotly.com/) for interactive visualizations.
- [PyTorch](https://pytorch.org/) for building the RNN model.
- [Hugging Face](https://huggingface.co/) for hosting the deployed model API.
- Inspired by open-source projects and the NBA analytics community.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.



