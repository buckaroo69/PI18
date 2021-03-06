import tensorflow as tf
from tensorflow.keras.layers import LayerNormalization
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Activation, Flatten, Conv2D, MaxPooling2D, Input, BatchNormalization
import time
import numpy as np
import requests
from tensorflow.keras.callbacks import Callback
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.models import model_from_json
from sklearn.model_selection import KFold
import pandas as pd
import arff
import re
import os
import urllib.request
import json
import sys
import pickle


#Env variables
parser_url = 'http://parser:6000' if "PARSER_URL" not in os.environ else os.environ['PARSER_URL']
deployer_url = 'http://deployer:7000/simulations/' if "DEPLOYER_DELETE_URL" not in os.environ else os.environ['DEPLOYER_DELETE_URL']

def main(model_json,conf_json):

    #Get configuration paramteres
    BATCH_SIZE = int(conf_json['batch_size'])
    EPOCHS = int(conf_json['epochs'])
    EPOCH_PERIOD = int(conf_json['epoch_period'])
    LEARNING_RATE = float(conf_json['learning_rate'])

    #Search directory for files dataset_test dataset_train
    for file_name in os.listdir():
        if 'dataset_test' in file_name:
            test_path = file_name
        if 'dataset_train' in file_name:
            train_path = file_name
        if 'dataset_val' in file_name:
            val_path = file_name


    def load_database(path_given,conf_json,type_file='train'):
        #File path given to file in VFS
        file_arr =  os.path.basename(path_given).split('.')
        file_name = file_arr[0]
        file_extension = file_arr[1]

        if 'csv' in file_arr[1]:
            label_name = conf_json['label_collumn']
            df = pd.read_csv(path_given)
            target = df.pop(label_name)
            features = df.values.tolist()
            labels = target.values.tolist()

            dataset = tf.data.Dataset.from_tensor_slices((features, labels))
            #If it's a csv it's expect of conf to have this extra
        elif 'arff' in file_arr[1]:

            label_name = conf_json['label_column']
            out = arff.load(open('dataset_val.arff', 'r'))
            attrs = [label for label,data_type in out['attributes']]
            df = pd.DataFrame(out['data'],columns =attrs)
            target = df.pop(label_name)
            features = df.values.tolist()
            labels = target.values.tolist()

            dataset = tf.data.Dataset.from_tensor_slices((features, labels))
        elif 'pickle' in file_arr[1] or 'zip' in file_arr[1]:
            #If pandas.Dataframe serialized as pickle

            df = pd.read_pickle(path_given)
            label_name = conf_json['label_column']

            target = df.pop(label_name)
            features = df.values.tolist()
            labels = target.values.tolist()

            dataset = tf.data.Dataset.from_tensor_slices((features, labels))
        elif 'json' in file_arr[1]:

            with open(path_given,'rb') as file_read:
                df = pd.read_json(file_read)
                #If it's a json file it's expect of conf to have this extra
                label_name = conf_json['label_column']
                target = df.pop(label_name)
                features = df.values.tolist()
                labels =  target.values.tolist()

                dataset = tf.data.Dataset.from_tensor_slices((features, labels))
        elif 'npz' in file_arr[1]:

            with np.load(path_given) as numpy_data:
                if type_file == "train":
                    feature_name = conf_json['train_feature_name']
                    label_name = conf_json['train_label_name']
                elif type_file == 'test':
                    feature_name = conf_json['test_feature_name']
                    label_name = conf_json['test_label_name']
                elif type_file == 'validation':
                    feature_name = conf_json['val_feature_name']
                    label_name = conf_json['val_label_name']

                features = numpy_data[feature_name]
                labels = numpy_data[label_name]
                dataset = tf.data.Dataset.from_tensor_slices((features, labels))
        else:
            #Non suported file extension
            dataset = None

        return dataset

    def get_chunk_k_fold(dataset_train,dataset_test,k_fold_number,k_fold_index):

        dataset_train_x = np.array([x for x,y in dataset_train.as_numpy_iterator()])
        dataset_train_y = np.array([y for x,y in dataset_train.as_numpy_iterator()])
        
        dataset_test_x = np.array([x for x,y in dataset_test.as_numpy_iterator()])
        dataset_test_y = np.array([y for x,y in dataset_test.as_numpy_iterator()])
        
        dataset_train_test_features = np.append(dataset_train_x,dataset_test_x, axis=0)
        dataset_train_test_labels = np.append(dataset_train_y,dataset_test_y, axis=0)


        kfold = KFold(n_splits=k_fold_number, shuffle=True, random_state=1048596)
        idx = 0
        for train_index, val_index in kfold.split(dataset_train_test_features):
            #Stratified fold for train and validation
            x_train_kf, x_val_kf = dataset_train_test_features[train_index], dataset_train_test_features[val_index]
            y_train_kf, y_val_kf = dataset_train_test_labels[train_index], dataset_train_test_labels[val_index]
            if idx == k_fold_index:
                #Get new datasets
                dataset_train = tf.data.Dataset.from_tensor_slices((x_train_kf, y_train_kf))
                dataset_val = tf.data.Dataset.from_tensor_slices((x_val_kf, y_val_kf))
                return dataset_train,dataset_val
            idx+=1

    dataset_train = load_database(train_path,conf_json)
    dataset_test = load_database(test_path,conf_json,type_file="test")
    dataset_val = load_database(val_path,conf_json,type_file="validation")



    if 'k-fold_index' in conf_json:

        dataset_train,dataset_val = get_chunk_k_fold(dataset_train,dataset_test,int(conf_json['k-fold_validation']),int(conf_json['k-fold_index']))

    #After k-chunk only
    dataset_train = dataset_train.shuffle(len(dataset_train)).batch(BATCH_SIZE)
    dataset_val = dataset_val.shuffle(len(dataset_val)).batch(BATCH_SIZE)
    dataset_test = dataset_test.shuffle(len(dataset_test)).batch(BATCH_SIZE)
    #Get URL to aggregator
    url = parser_url

    def get_optimizer_tensorflow(conf_json,base_learning_rate):
        config = conf_json['optimizer_conf']

        config = parse_conf_dictionary(config)
        identifier = {"class_name": conf_json['optimizer'].lower(),
                               "config": config}
        optimizer = tf.keras.optimizers.get(identifier)
        return optimizer

    def get_loss_func_tensorflow(conf_json):

        config = conf_json['loss_function_conf']

        config = parse_conf_dictionary(config)
        identifier = {"class_name": conf_json['loss_function'],
                "config": config}
        loss = tf.keras.losses.get(identifier)
        return loss

    def parse_conf_dictionary(config):

        for key in config.keys():
            if not type(config[key]) is str:
                continue
            value = config[key].lower()
            if 'true' in value:
                config[key] = True
            elif 'false' in value:
                config[key] = False
            elif value.isnumeric():
                config[key] = float(value)

        return config

    def get_metrics_tensorflow(conf_json):

        metrics_lst_json = conf_json['metrics']
        metrics_lst_class = []
        for metrics_json in metrics_lst_json:
            metric_name = metrics_json['metric']
            conf_metric = metrics_json['conf']
            #We already add accuracy and leave which one to be decided by framework
            if metric_name in ['BinaryAccuracy', 'Accuracy', 'TopKCategoricalAccuracy' 'CategoricalAccuracy', 'SparseCategoricalAccuracy']:
                continue
            conf_metric = parse_conf_dictionary(conf_metric)
            identifier = {"class_name": metric_name,
                "config": conf_metric}
            metrics_class = tf.keras.metrics.get(identifier)
            metrics_lst_class.append(metrics_class)
        #Default one
        metrics_lst_class.append('accuracy')
        return metrics_lst_class

    optimizer_choosen = get_optimizer_tensorflow(conf_json,LEARNING_RATE)
    loss_function_choosen = get_loss_func_tensorflow(conf_json)

    #Get Model
    model = model_from_json(model_json)
    #Get Metrics
    metrics = get_metrics_tensorflow(conf_json)
    model.compile(optimizer=optimizer_choosen,
                loss=loss_function_choosen,
                metrics=metrics)
    json_model = model_json

    #Used because keras seems to use both lists and numpy arrays in weights
    def listify_numpy_arr(lst):
        if not isinstance(lst,list) and 'numpy.ndarray' not in str(type(lst)):
            return lst
        for i in range(len(lst)):
            if 'numpy.ndarray' in str(type(lst[i])):
                lst[i] = listify_numpy_arr(lst[i].tolist())
            else:
                lst[i] = listify_numpy_arr(lst[i])
        return lst

    class DataAggregateCallback(tf.keras.callbacks.Callback):
        def on_epoch_end(self, epoch, logs=None):
            if epoch % EPOCH_PERIOD == 0 or epoch == EPOCHS-1:

                logs = {i : logs[i] for i in logs.keys()}


                weigths = []
                #get_weights already gives two arrays, first is actual weights, the rest are bias(non-treinable weights)
                for i in range(len(model.layers)):
                    if model.layers[i].weights != None:
                        out = listify_numpy_arr(model.layers[i].get_weights())
                        weigths.append(out)


                res_dic = {}
                
                res_dic["model"] = json_model

                res_dic["logs"] = logs

                if 'k-fold_index' in conf_json:                
                    k_fold_idx = int(conf_json["k-fold_index"])
                    res_dic["sim_id"] = conf_json["k-fold_ids"][k_fold_idx]
                else:
                    res_dic["sim_id"] = conf_json["id"]

                res_dic["epoch"] = epoch

                res_dic["weights"] = weigths

                data = res_dic

                url = parser_url+'/update'
                if epoch == EPOCHS-1:
                    url = parser_url+'/finish'
                try:
                    headers = {'Content-type': 'application/json'}
                    res = requests.post(url, json = data,headers=headers,timeout=50)

                except Exception as error:
                    print(error)
                    raise error

    model.fit(dataset_train, batch_size=BATCH_SIZE, epochs=EPOCHS
            , callbacks= [DataAggregateCallback()], validation_data=dataset_val)
    model.evaluate(dataset_test, batch_size=BATCH_SIZE, verbose=0)

#Read files from pre-defined directory
DIR_FILES = "."
with open(os.path.join(DIR_FILES,"model.json"),"r") as model_file:
    model_json = model_file.read()
with open(os.path.join(DIR_FILES,"conf.json"),"r") as conf_file:
    conf_txt = conf_file.read()
    conf_json = json.loads(conf_txt)

#Send last 490 chars for error, limit in DB is 500
LIMIT_ERROR = 490
try:
    main(model_json,conf_json)
except Exception as error:
    print('ERROR during simulation')
    error_sent = str(error)[-LIMIT_ERROR:]
    data = {}

    data['id'] = conf_json["id"]
    data['error'] = error_sent
    url = parser_url+'/send_error'
    headers = {'Content-type': 'application/json'}
    res = requests.post(url, json = data,headers=headers,timeout=50)


#Delete sim after running
urlDelete = deployer_url + conf_json["id"]
res = requests.delete(urlDelete)
print('Delete status:', res, file=sys.stderr)