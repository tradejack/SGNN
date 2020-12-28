# AUTOGENERATED! DO NOT EDIT! File to edit: 00_core.ipynb (unless otherwise specified).

__all__ = ['import_data', 'MyRBP', 'build_preprocessor', 'build_keras_model', 'main', 'EPOCHS', 'BATCH_SIZE',
           'data_filepath']

# Cell
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

def import_data(filepath):
    data = pd.read_csv(data_filepath)
    data = data.dropna(axis=0)  # Drop rows with NA values
    y = data.DamslActTag
    X = data.Text

    # Convert labels to categories
    le = LabelEncoder()
    y = le.fit_transform(y)

    return X, y

# Cell
import scipy.sparse as sp
import random as rand
from sklearn.base import BaseEstimator
import numpy as np
import scipy.sparse
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from nearpy.hashes import RandomBinaryProjections

class MyRBP(BaseEstimator, RandomBinaryProjections):
    rand_seed = None  # Declare it as class variable
    def __init__(self, hash_name='hasher', projection_count=1, rand_seed=None):
        RandomBinaryProjections.__init__(self, hash_name, projection_count, rand_seed=rand_seed)

    def fit(self, X, y):
        self.rand = np.random.RandomState(self.rand_seed)  # rand seed after param setting
        self.reset(X.shape[1])

    def transform(self, X):
        return self.hash_vector(X)

    def fit_transform(self, X, y):
        self.fit(X, y)
        return self.transform(X)

    def hash_vector(self, v, querying=False):
        """
        Hashes the vector and returns the binary bucket key as string.
        """
        if scipy.sparse.issparse(v):
            # If vector is sparse, make sure we have the CSR representation
            # of the projection matrix
            if self.normals_csr == None:
                self.normals_csr = scipy.sparse.csr_matrix(self.normals)
            # Make sure that we are using CSR format for multiplication
            if not scipy.sparse.isspmatrix_csr(v):
                v = scipy.sparse.csr_matrix(v)
            # Project vector onto all hyperplane normals
            # projection = self.normals_csr.dot(v)
            projection = v.dot(scipy.sparse.csr_matrix.transpose(self.normals_csr))
        else:
            # Project vector onto all hyperplane normals
            projection = np.dot(v, np.matrix.transpose(self.normals))
        # Return binary key
        return projection > 0

# Cell

def build_preprocessor(T=80, d=14, char_ngram_range=(1, 4)):
    # T=80 projections for each of dimension d=14: 80 * 14 = 1120-dimensionnal word projections

    char_term_frequency_params = {
        'char_term_frequency__analyzer': 'char',
        'char_term_frequency__lowercase': True,
        'char_term_frequency__ngram_range': char_ngram_range,
        'char_term_frequency__strip_accents': None,
        'char_term_frequency__min_df': 2,
        'char_term_frequency__max_df': 0.99,
        'char_term_frequency__max_features': int(1e7),
    }

    rand_seeds = [rand.randint(0,T*100) for i in range(T)] # Need a different seed for each hasher

    hashing_feature_union_params = {
        **{'union__random_binary_projection_hasher_{}__projection_count'.format(t): d
           for t in range(T)
        },
        **{'union__random_binary_projection_hasher_{}__hash_name'.format(t): 'hasher' + str(t)
           for t in range(T)
        },
        **{'union__random_binary_projection_hasher_{}__rand_seed'.format(t): rand_seeds[t]  # only AFTER hashing.
           for t in range(T)
        }
    }

    preprocessor = Pipeline([
        ("char_term_frequency", CountVectorizer()),
        ('union', FeatureUnion([
            ('random_binary_projection_hasher_{}'.format(t), MyRBP())
            for t in range(T)
        ]))
    ])

    params = dict()
    params.update(char_term_frequency_params)
    params.update(hashing_feature_union_params)
    preprocessor.set_params(**params)
    return preprocessor

# Cell
import tensorflow as tf

def build_keras_model(train_labels):
    model = tf.keras.Sequential()
    model.add(tf.keras.layers.Dense(256, activation=tf.nn.sigmoid, input_shape=(1120,)))
    model.add(tf.keras.layers.Dropout(0.25))
    model.add(tf.keras.layers.Dense(256, activation=tf.nn.sigmoid))
    model.add(tf.keras.layers.Dropout(0.25))
    model.add(tf.keras.layers.Dense(train_labels.shape[1], activation=tf.nn.softmax))

    # Cosine annealing decay
    lr_schedule = tf.keras.experimental.CosineDecay(0.025, decay_steps=1000000)
    # SGD optimizer with Nesterov momentum
    opt = tf.keras.optimizers.SGD(nesterov=True, learning_rate=lr_schedule)
    #opt = tf.keras.optimizers.SGD(nesterov=True)
    model.compile(loss='categorical_crossentropy',
                  optimizer=opt,
                  metrics=['accuracy'])

    return model

# Cell
EPOCHS=50
BATCH_SIZE=100
data_filepath = "/home/andres/repositories/SGNN/data/swda-acttags-and-text.csv"

def main():
    X, y = import_data(data_filepath)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y)

    # Convert categories to one-hot-encodings, as apparently needed by keras
    train_labels = tf.keras.utils.to_categorical(y_train)
    test_labels = tf.keras.utils.to_categorical(y_test)

    preprocessor = build_preprocessor()
    keras_model = build_keras_model(train_labels)

    train_features = preprocessor.fit_transform(X_train)

    keras_model.fit(train_features, train_labels, epochs=EPOCHS, batch_size=BATCH_SIZE)
    test_features = preprocessor.transform(X_test)
    keras_model.evaluate(test_features, test_labels)

# Cell
main()