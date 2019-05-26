from keras.layers import Dense, LSTM, Embedding, Dropout
from keras import backend
from keras.models import *
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from utils import getActivationValue,layerName, hard_sigmoid
from keract import get_activations_single_layer


def rmse(y_true, y_pred):
	return backend.sqrt(backend.mean(backend.square(y_pred - y_true), axis=-1))

class lipoClass:
    def __init__(self):
        self.data = None
        self.X_orig = None
        self.X = None
        self.Y = None
        self.X_train = None
        self.y_train = None
        self.X_test = None
        self.y_test = None
        self.model = None
        self.unique_chars = None
        self.char_to_int = None
        self.int_to_char = None
        self.pad = 0
        self.numAdv = 0
        self.numSamples = 0
        self.perturbations = []

    def load_data(self):
        self.data = pd.read_csv("dataset/Lipophilicity.csv")
        self.pre_processing()
        self.smile_dict()
        self.pad = len(max(self.X_orig, key=len))
        self.X = self.smile_vect(self.X_orig)
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(self.X,self.Y,test_size = 0.2,random_state=2)


    def pre_processing(self):
        self.X_orig = np.array(self.data.smiles)
        self.Y = np.array(self.data.exp)
        index = [i for i in range(len(self.X_orig)) if len(self.X_orig[i]) <= 80]
        self.X_orig = self.X_orig[index]
        self.Y = self.Y[index]

    def smile_dict(self):
        raw_data = ''.join(self.X_orig)
        self.unique_chars = sorted(list(set(raw_data)))
        # maps each unique character as int
        self.char_to_int = dict((c, i + 1) for i, c in enumerate(self.unique_chars))
        # int to char dictionary
        self.int_to_char = dict((i + 1, c) for i, c in enumerate(self.unique_chars))

    def smile_vect(self,X):
        new_X = np.zeros((X.shape[0], self.pad), dtype=np.int8)
        for i, ss in enumerate(X):
            l = len(ss)
            diff = self.pad - l
            for j, c in enumerate(ss):
                new_X[i, j + diff] = self.char_to_int[c]
        return new_X

    def load_model(self):
        self.model = load_model('models/Lipo.h5',custom_objects={'rmse': rmse})
        self.model.compile(loss='mean_squared_error', optimizer='adam',metrics=[rmse])
        self.model.summary()

    def layerName(self, layer):
        layerNames = [layer.name for layer in self.model.layers]
        return layerNames[layer]

    def train_model(self):
        self.load_data()
        char_num = len(self.unique_chars) + 1
        embedding_vector_length = 8
        self.model = Sequential()
        self.model.add(Embedding(char_num, embedding_vector_length, input_length=self.pad))
        self.model.add(LSTM(64))
        self.model.add(Dropout(0.2))
        self.model.add(Dense(1, activation="linear"))
        self.model.compile(loss='mean_squared_error', optimizer='adam', metrics=[rmse])
        print(self.model.summary())
        self.model.fit(self.X_train,self.y_train, validation_data=(self.X_test,self.y_test), nb_epoch=300, batch_size=32)
        self.model.save('Lipo.h5')

    def vect_smile(self,vect):
        smiles = []
        for v in vect:
            # mask v
            v = filter(None, v)
            # Find one hot encoded index with argmax, translate to char and join to string
            smile = "".join(self.int_to_char[i] for i in v)
            smiles.append(smile)
        return np.array(smiles)

    def displayInfo(self,test):
        test = test[np.newaxis, :]
        output_value = np.squeeze(self.model.predict(test))
        print("current prediction: ", output_value)
        return output_value

    def updateSample(self,pred1,pred2,m,o):
        if abs(pred1-pred2) >= 1 and o == True:
            self.numAdv += 1
            self.perturbations.append(m)
        self.numSamples += 1
        self.displaySuccessRate()

    def displaySamples(self):
        print("%s samples are considered" % (self.numSamples))

    def displaySuccessRate(self):
        print("%s samples, within which there are %s adversarial examples" % (self.numSamples, self.numAdv))
        print("the rate of adversarial examples is %.2f\n" % (self.numAdv / self.numSamples))

    def displayPerturbations(self):
        if self.numAdv > 0:
            print("the average perturbation of the adversarial examples is %s" % (sum(self.perturbations) / self.numAdv))
            print("the smallest perturbation of the adversarial examples is %s" % (min(self.perturbations)))


    # calculate the lstm hidden state and cell state manually
    def cal_hidden_state(self, test):
        acx = get_activations_single_layer(self.model, np.array([test]), self.layerName(0))
        units = int(int(self.model.layers[1].trainable_weights[0].shape[1]) / 4)
        # print("No units: ", units)
        # lstm_layer = model.layers[1]
        W = self.model.layers[1].get_weights()[0]
        U = self.model.layers[1].get_weights()[1]
        b = self.model.layers[1].get_weights()[2]

        W_i = W[:, :units]
        W_f = W[:, units: units * 2]
        W_c = W[:, units * 2: units * 3]
        W_o = W[:, units * 3:]

        U_i = U[:, :units]
        U_f = U[:, units: units * 2]
        U_c = U[:, units * 2: units * 3]
        U_o = U[:, units * 3:]

        b_i = b[:units]
        b_f = b[units: units * 2]
        b_c = b[units * 2: units * 3]
        b_o = b[units * 3:]

        # calculate the hidden state value
        h_t = np.zeros((self.pad, units))
        c_t = np.zeros((self.pad, units))
        f_t = np.zeros((self.pad, units))
        h_t0 = np.zeros((1, units))
        c_t0 = np.zeros((1, units))

        for i in range(0, self.pad):
            f_gate = hard_sigmoid(np.dot(acx[i, :], W_f) + np.dot(h_t0, U_f) + b_f)
            i_gate = hard_sigmoid(np.dot(acx[i, :], W_i) + np.dot(h_t0, U_i) + b_i)
            o_gate = hard_sigmoid(np.dot(acx[i, :], W_o) + np.dot(h_t0, U_o) + b_o)
            new_C = np.tanh(np.dot(acx[i, :], W_c) + np.dot(h_t0, U_c) + b_c)
            c_t0 = f_gate * c_t0 + i_gate * new_C
            h_t0 = o_gate * np.tanh(c_t0)
            c_t[i, :] = c_t0
            h_t[i, :] = h_t0
            f_t[i, :] = f_gate

        return h_t, c_t, f_t











