# Department Classifier — Training Report

Total examples: 246 across 10 specialties (built directly from `specialties.SPECIALTIES`)

Train/Val/Test split: 172/37/37 (stratified, random_state=42)

## LogReg (val)

- Accuracy: 0.973
- Macro-F1: 0.975

```
                            precision    recall  f1-score   support

                Cardiology       1.00      1.00      1.00         4
               Dermatology       1.00      1.00      1.00         4
                       ENT       1.00      1.00      1.00         4
          Gastroenterology       1.00      1.00      1.00         4
          General Medicine       1.00      0.75      0.86         4
                Gynecology       1.00      1.00      1.00         3
                 Neurology       0.80      1.00      0.89         4
               Orthopedics       1.00      1.00      1.00         3
Psychiatry / Mental Health       1.00      1.00      1.00         3
               Pulmonology       1.00      1.00      1.00         4

                  accuracy                           0.97        37
                 macro avg       0.98      0.97      0.97        37
              weighted avg       0.98      0.97      0.97        37

```

## LogReg (test)

- Accuracy: 0.919
- Macro-F1: 0.915

```
                            precision    recall  f1-score   support

                Cardiology       1.00      0.67      0.80         3
               Dermatology       1.00      1.00      1.00         4
                       ENT       1.00      1.00      1.00         3
          Gastroenterology       0.80      1.00      0.89         4
          General Medicine       1.00      0.75      0.86         4
                Gynecology       1.00      1.00      1.00         4
                 Neurology       1.00      0.75      0.86         4
               Orthopedics       1.00      1.00      1.00         4
Psychiatry / Mental Health       0.80      1.00      0.89         4
               Pulmonology       0.75      1.00      0.86         3

                  accuracy                           0.92        37
                 macro avg       0.93      0.92      0.91        37
              weighted avg       0.94      0.92      0.92        37

```

## Majority-class baseline (test)

- Accuracy: 0.108
- Macro-F1: 0.020

```
                            precision    recall  f1-score   support

                Cardiology       0.00      0.00      0.00         3
               Dermatology       0.00      0.00      0.00         4
                       ENT       0.00      0.00      0.00         3
          Gastroenterology       0.00      0.00      0.00         4
          General Medicine       0.00      0.00      0.00         4
                Gynecology       0.00      0.00      0.00         4
                 Neurology       0.11      1.00      0.20         4
               Orthopedics       0.00      0.00      0.00         4
Psychiatry / Mental Health       0.00      0.00      0.00         4
               Pulmonology       0.00      0.00      0.00         3

                  accuracy                           0.11        37
                 macro avg       0.01      0.10      0.02        37
              weighted avg       0.01      0.11      0.02        37

```

## Confusion matrix (test set, LogReg)

Label order: ['Cardiology', 'Dermatology', 'ENT', 'Gastroenterology', 'General Medicine', 'Gynecology', 'Neurology', 'Orthopedics', 'Psychiatry / Mental Health', 'Pulmonology']

```
[2, 0, 0, 0, 0, 0, 0, 0, 0, 1]
[0, 4, 0, 0, 0, 0, 0, 0, 0, 0]
[0, 0, 3, 0, 0, 0, 0, 0, 0, 0]
[0, 0, 0, 4, 0, 0, 0, 0, 0, 0]
[0, 0, 0, 1, 3, 0, 0, 0, 0, 0]
[0, 0, 0, 0, 0, 4, 0, 0, 0, 0]
[0, 0, 0, 0, 0, 0, 3, 0, 1, 0]
[0, 0, 0, 0, 0, 0, 0, 4, 0, 0]
[0, 0, 0, 0, 0, 0, 0, 0, 4, 0]
[0, 0, 0, 0, 0, 0, 0, 0, 0, 3]
```

## Notes
This dataset is generated programmatically from the project's own symptom-keyword map rather than hand-labeled patient data, so treat these metrics as a pipeline validation, not a clinical-grade evaluation. For a submission-grade evaluation, augment with a curated public symptom-checker dataset and re-run this script.