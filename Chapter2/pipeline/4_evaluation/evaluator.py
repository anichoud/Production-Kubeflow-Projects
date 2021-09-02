import click
import os
import dill
import json
import logging
import time
import tensorflow as tf
from pickle import load
import pandas as pd
from sklearn import metrics
from sklearn.metrics import confusion_matrix
from tensorflow.python.lib.io import file_io
from sklearn.metrics import roc_curve, auc
from sklearn import metrics as ms


@click.command()
@click.option('--test-file', default="/mnt/test.data")
@click.option('--test-target', default="/mnt/testtarget.data")
@click.option('--probability', default=0.5)
@click.option('--model-output-base-path', default="/mnt/saved_model")
@click.option('--gcs-path', default="gs://kubeflowusecases/breast/model")
@click.option('--gcs-path-confusion', default="gs://kubeflowusecases/breast/")
def evaluator_model(test_file,test_target,model_output_base_path,gcs_path,probability,gcs_path_confusion):
        
        with open(test_file, 'rb') as in_f:
            test= dill.load(in_f)
     
        with open(test_target, 'rb') as in_f:
            test_tar= dill.load(in_f) 

        
        new_model = tf.keras.models.load_model(model_output_base_path)
        # Check its architecture
        print(new_model.summary())

        ann_prediction = new_model.predict(test)
        ann_prediction = (ann_prediction > probability)*1 

        # Compute error between predicted data and true response and display it in confusion matrix
        acc_ann = round(ms.accuracy_score(test_tar, ann_prediction) * 100, 2)
        print(acc_ann)
        metrics = {
                'metrics': [{
                    'name': 'Accuracy',
                    'numberValue':  acc_ann,
                    'format': "RAW",
                }]}    

        with open('/mlpipeline-metrics.json', 'w') as f:
            json.dump(metrics,f)
        
        vocab =[0,1]
        cm = confusion_matrix(test_tar, ann_prediction > probability,labels=vocab)


        data_conf= []
        for target_index, target_row in enumerate(cm):
            for predicted_index, count in enumerate(target_row):
                  data_conf.append((vocab[target_index], vocab[predicted_index], count))
    
        
        df_cm = pd.DataFrame(data_conf, columns=['target', 'predicted', 'count'])
        cm_file = os.path.join(gcs_path_confusion, 'confusion_matrix.csv')
        with file_io.FileIO(cm_file, 'w') as f:
            df_cm.to_csv(f, columns=['target', 'predicted', 'count'], header=False, index=False)   
        
        false_positive_rate, true_positive_rate, thresholds = roc_curve(test_tar, ann_prediction)

        df_roc = pd.DataFrame({'fpr': false_positive_rate, 'tpr': true_positive_rate, 'thresholds': thresholds})
        roc_file = os.path.join(gcs_path_confusion, 'roc.csv')
        with file_io.FileIO(roc_file, 'w') as f:
            df_roc.to_csv(f, columns=['fpr', 'tpr', 'thresholds'], header=False,            index=False)

        metadata = {
                'outputs' : [{
                'type': 'confusion_matrix',
                'format': 'csv',
                'schema': [
                    {'name': 'target', 'type': 'CATEGORY'},
                    {'name': 'predicted', 'type': 'CATEGORY'},
                    {'name': 'count', 'type': 'NUMBER'},
                ],
                'source': cm_file,
                # Convert vocab to string because for bealean values we want "True|False" to match csv data.
                'labels': list(map(str, vocab)),
                },
                {
            'type': 'roc',
            'format': 'csv',
            'schema': [
                {'name': 'fpr', 'type': 'NUMBER'},
                {'name': 'tpr', 'type': 'NUMBER'},
                {'name': 'thresholds', 'type': 'NUMBER'},
            ],
            'source': roc_file
            }]
            }
        with open('/mlpipeline-ui-metadata.json', 'w') as f:
            json.dump(metadata, f)

        
        

        return

if __name__ == "__main__":
    evaluator_model()