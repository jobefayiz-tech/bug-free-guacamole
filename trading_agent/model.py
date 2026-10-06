import numpy as np


class LogisticModel:
    """Small dependency-free logistic regression (probability the trade works)."""

    def __init__(self, lr=0.1, epochs=300, l2=1e-3):
        self.lr, self.epochs, self.l2 = lr, epochs, l2
        self.w = self.b = self.mu = self.sd = None

    def fit(self, X, y):
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Z = (X - self.mu) / self.sd
        self.w, self.b = np.zeros(Z.shape[1]), 0.0
        for _ in range(self.epochs):
            p = 1 / (1 + np.exp(-(Z @ self.w + self.b)))
            g = p - y
            self.w -= self.lr * (Z.T @ g / len(y) + self.l2 * self.w)
            self.b -= self.lr * g.mean()
        return self

    def predict_proba(self, X):
        Z = (np.asarray(X, float) - self.mu) / self.sd
        return 1 / (1 + np.exp(-(Z @ self.w + self.b)))
