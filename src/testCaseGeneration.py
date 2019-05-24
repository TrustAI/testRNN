import keras
from keras.datasets import imdb 
from keras.layers import *
from keras import *
from keras.models import *
import numpy as np
import random
import pickle
import copy
import keras.backend as K
from keras.preprocessing import sequence 
from keract import * 
from utils import *

    
def getNextInputByGradient(f,nodes_names,sm,epsilon,test,lastactivation,step):
    model = sm.model
    # print("test shape: %s, lastactivation shape %s"%(str(test.shape),str(lastactivation.shape)))
    gd = cal_gradient(model,f,np.array([test]),np.array([lastactivation]),nodes_names)
    gd = np.squeeze(list(gd.values())[0])
    newtest = test + epsilon * np.sign(gd)
    newtest = np.clip(newtest,0,1)
    lastactivation = np.squeeze(sm.model.predict(newtest[np.newaxis, :]))
    step = step - 1

    if np.array_equal(test,newtest):
        print("Gradients are too small")
        print("-----------------------------------------------------")
        return None
    elif step <= 0:
        print("found a test case of shape %s!"%(str(newtest.shape)))
        return newtest
    else :
        return getNextInputByGradient(f, nodes_names, sm, epsilon, newtest, lastactivation, step)

def getNextInputByGradientAndFeatures(sm,epsilon,layer1,layer2,g1,b1,g2,b2,feature1,feature2,test1,test2,lastactivation2,n): 

    model = sm.model
    
    print("test shape: %s, lastactivation shape %s"%(str(test1.shape),str(lastactivation2.shape)))
    act1x = get_activations_single_layer(model,np.array([test1]),sm.layerName(layer1))
    act1y = get_activations_single_layer(model,np.array([test1]),sm.layerName(layer2))
    act1x, opp_act1x = getFeatureFromLayer(act1x,feature1)
    act1y, _ = getFeatureFromLayer(act1y,feature2)
    
    gd = get_gradients_of_activations_input(model,np.array([test2]),np.array([lastactivation2]),sm.layerName(0))
    gd = np.squeeze(list(gd.values())[0])
    newtest = np.round(test2[0] - epsilon * gd)
    act2x = get_activations_single_layer(model,np.array([newtest]),sm.layerName(layer1))
    act2y = get_activations_single_layer(model,np.array([newtest]),sm.layerName(layer2))
    act2x, opp_act2x = getFeatureFromLayer(act2x,feature1)
    act2y, _ = getFeatureFromLayer(act2y,feature2)    

    lastactivation2 = get_activations_single_layer(model,np.array([newtest]),sm.layerName(-1))

    if g1(act1x,act2x) > b1 and g2(act1y,act2y) > b2 and g1(opp_act1x,opp_act2x) <= b1 : 
        print("found a test case of shape %s!"%(str(newtest.shape)))
        return newtest
    elif g1(act1x,act2x) > 10* b1 or g2(act1y,act2y) > 10 * b2 or n > 10: 
        print("failed to find a test case in this round! (current distances are %.4f and %.4f and %.4f) "%(g1(act1x,act2x),g2(act1y,act2y),g1(opp_act1x,opp_act2x)))
        return None
    elif np.array_equal(test2,newtest):
        print("enlarge the epsilon by 10 times, and continue ... (current distances are %.4f and %.4f and %.4f)"%(g1(act1x,act2x),g2(act1y,act2y),g1(opp_act1x,opp_act2x)))
        return getNextInputByGradientAndFeatures(sm,epsilon*10,layer1,layer2,g1,b1,g2,b2,feature1,feature2,test1,newtest,lastactivation2, n+1)
    else: 
        print("moving a step away, and continue ... (current distances are %.4f and %.4f and %.4f) "%(g1(act1x,act2x),g2(act1y,act2y),g1(opp_act1x,opp_act2x)))
        return getNextInputByGradientAndFeatures(sm,epsilon,layer1,layer2,g1,b1,g2,b2,feature1,feature2,test1,newtest,lastactivation2, n+1)



def getNextInputByCustomisedFunction(sm,fn,epsilon,layer1,layer2,g1,b1,g2,b2,test1,test2,n):
    model = sm.model 
    act1x = get_activations_single_layer(model,np.array([test1]),sm.layerName(layer1))
    act1y = get_activations_single_layer(model,np.array([test1]),sm.layerName(layer2))

    gd = fn([np.array([test2])])
    newtest = np.round(test2 - epsilon * gd[0][0])
    
    act2x = get_activations_single_layer(model,np.array([newtest]),sm.layerName(layer1))
    act2y = get_activations_single_layer(model,np.array([newtest]),sm.layerName(layer2))
        
    if g1(act1x,act2x) > b1 and g2(act1y,act2y) > b2: 
        print("found a test case of shape %s!"%(str(newtest.shape)))
        return newtest
    elif g1(act1x,act2x) > 10* b1 or g2(act1y,act2y) > 10 * b2 or n > 10: 
        print("failed to find a test case in this round! (current distances are %.4f and %.4f)"%(g1(act1x,act2x),g2(act1y,act2y)))
        return None
    elif np.array_equal(test2,newtest):
        print("enlarge the epsilon by 10 times, and continue ... (current distances are %.4f and %.4f)"%(g1(act1x,act2x),g2(act1y,act2y)))
        return getNextInputByCustomisedFunction(sm,fn,epsilon*10,layer1,layer2,g1,b1,g2,b2,test1,newtest, n+1)
    else: 
        print("moving a step away, and continue ... (current distances are %.4f and %.4f)"%(g1(act1x,act2x),g2(act1y,act2y)))
        return getNextInputByCustomisedFunction(sm,fn,epsilon,layer1,layer2,g1,b1,g2,b2,test1,newtest, n+1)
        
        
def getNextInputByCustomisedFunctionAndFeatures(sm,fn,epsilon,layer1,layer2,g1,b1,g2,b2,feature1,feature2,test1,test2, n):
    model = sm.model 
    act1x = get_activations_single_layer(model,np.array([test1]),sm.layerName(layer1))
    act1y = get_activations_single_layer(model,np.array([test1]),sm.layerName(layer2))
    #print("shape1: %s"%(str(act1x.shape)))
    #print("shape2: %s"%(str(act1y.shape)))
    act1x, opp_act1x = getFeatureFromLayer(act1x,feature1)
    act1y, _ = getFeatureFromLayer(act1y,feature2)

    gd = fn([np.array([test2])])
    newtest = np.round(test2 - epsilon * gd[0][0])
    
    act2x = get_activations_single_layer(model,np.array([newtest]),sm.layerName(layer1))
    act2y = get_activations_single_layer(model,np.array([newtest]),sm.layerName(layer2))
    act2x, opp_act2x = getFeatureFromLayer(act2x,feature1)
    act2y, _ = getFeatureFromLayer(act2y,feature2)
        
    if g1(act1x,act2x) > b1 and g2(act1y,act2y) > b2 and g1(opp_act1x,opp_act2x) <= b1: 
        print("found a test case of shape %s!"%(str(newtest.shape)))
        return newtest
    elif g1(act1x,act2x) > 10* b1 or g2(act1y,act2y) > 10 * b2 or n > 10: 
        print("failed to find a test case in this round! (current distances are %.4f and %.4f and %.4f)"%(g1(act1x,act2x),g2(act1y,act2y),g1(opp_act1x,opp_act2x)))
        return None
    elif np.array_equal(test2,newtest):
        print("enlarge the epsilon by 10 times, and continue ... (current distances are %.4f and %.4f and %.4f)"%(g1(act1x,act2x),g2(act1y,act2y),g1(opp_act1x,opp_act2x)))
        return getNextInputByCustomisedFunctionAndFeatures(sm,fn,epsilon*10,layer1,layer2,g1,b1,g2,b2,feature1,feature2,test1,newtest, n+1)
    else: 
        print("moving a step away, and continue ... (current distances are %.4f and %.4f and %.4f)"%(g1(act1x,act2x),g2(act1y,act2y),g1(opp_act1x,opp_act2x)))
        return getNextInputByCustomisedFunctionAndFeatures(sm,fn,epsilon,layer1,layer2,g1,b1,g2,b2,feature1,feature2,test1,newtest, n+1)
        
        
def getFeatureFromLayer(activations,feature): 
    activations1 = copy.deepcopy(activations)
    featureActivation = []
    for i in feature: 
        if len(activations.shape) == 1:
            l = i[0]
            activations1[l] = 0 
        elif len(activations.shape) == 2:
            l = (i[0],i[1])
            activations1[i[0]][i[1]] = 0 
        else:
            print("getFeatureFromLayer: more than can be handled ")
            exit()
        featureActivation.append(activations.item(l))
    return featureActivation, activations1

def word_replacement(sm,test,goog_lm,dataset,dist_mat):
    review = sm.fromIDToText(test)
    wordclass = review.split(" ")
    index = random.sample(range(1, len(wordclass) - 1), 5)
    print(index)
    for i in index:
        src_word = dataset.dict[wordclass[i]]
        nearest, nearest_dist = glove_utils.pick_most_similar_words(src_word, dist_mat, 20)
        nearest_w = [dataset.inv_dict[x] for x in nearest]
        prefix = wordclass[i - 1]
        suffix = wordclass[i + 1]
        lm_preds = goog_lm.get_words_probs(prefix, nearest_w, suffix)
        probword = nearest_w[np.argmax(lm_preds)]
        print(probword)
        wordclass = [probword if x == wordclass[i] else x for x in wordclass]
    review1 = ' '.join(wordclass)
    tmp = sm.fromTextToID(review1)
    test2 = np.squeeze(sm.pre_processing_x(tmp))
    return test2
    
