from flask import Flask, request
import random
import torch
from transformers import AutoTokenizer, ElectraForSequenceClassification, pipeline

app = Flask(__name__)

# Load the model and tokenizer for sentiment analysis
tokenizer = AutoTokenizer.from_pretrained("monologg/koelectra-base-v3-discriminator")
model = ElectraForSequenceClassification.from_pretrained("monologg/koelectra-base-v3-discriminator", num_labels=4)
model.to(device)
model.load_state_dict(torch.load("model.pt", map_location=device))

# Load the GPT model
gpt_model_name = "gpt2"  # Example model name, replace with your desired GPT model
gpt_pipeline = pipeline("text-generation", model=gpt_model_name, tokenizer=gpt_model_name)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def predict_sentiment(text):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True).to(device)
    outputs = model(**inputs)
    predicted_class = torch.argmax(outputs.logits).item()
    predicted_prob = torch.softmax(outputs.logits, dim=1)[0][predicted_class].item()
    return predicted_class, predicted_prob

@app.route('/')
def index():
    message = request.args.get('message', '')
    if message:
        sentiment_class, sentiment_prob = predict_sentiment(message)
        if sentiment_prob < 0.25:
            gpt_response = gpt_pipeline(message, max_length=50, num_return_sequences=1)[0]['generated_text']
            return gpt_response
        else:
            response_type = sentiment_class
    else:
        response_type = random.randint(0, 4)  # If message parameter is missing, respond randomly

    return str(response_type)

if __name__ == '__main__':
    app.run(debug=True)
