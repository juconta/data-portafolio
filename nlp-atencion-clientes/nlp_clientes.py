import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score

# cargar dataset
df = pd.read_csv("mensajes_clientes.csv")

X = df["mensaje"]
y = df["categoria"]

# convertir texto a vectores
vectorizer = CountVectorizer()
X_vector = vectorizer.fit_transform(X)

# dividir datos
X_train, X_test, y_train, y_test = train_test_split(X_vector, y, test_size=0.3)

# entrenar modelo
model = MultinomialNB()
model.fit(X_train, y_train)

# predicción
predictions = model.predict(X_test)

# evaluar
accuracy = accuracy_score(y_test, predictions)

print("Precisión del modelo:", accuracy)

# probar con un mensaje nuevo
mensaje_nuevo = ["No puedo conectarme a internet"]
mensaje_vector = vectorizer.transform(mensaje_nuevo)

prediccion = model.predict(mensaje_vector)

print("Categoría predicha:", prediccion[0])