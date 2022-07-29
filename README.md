# NBA-Player-Perfomance-Prediction
![NBA logo](https://user-images.githubusercontent.com/96085690/152583881-36edffd9-4371-4b97-b476-a363e475c5b7.png)

Simple RNN model predicting the perfomance of an NBA player, based on the 10 previous games

The model was trained using the individual statistics of the NBA players, played between 2004 - 2022 seasons. 
As target value the PLUS_MINUS feature was used. 
Additionally, two more features were added: REST (days that a player had to rest before next game) and W_PCT (win percentage of the opposing team).

To test the model previous games of Dirk Nowitzki were used.
![My Image2](https://github.com/aggtamv/NBA-Player-Perfomance-Prediction/blob/main/test_prediction.png)

Although the model's predictions are not identical to the actual data, usefull insights can be derived from the current analysis, as someone can 
identify whether a player is underperfoming when expected to play well, or on the other hand overperfoming when he was expected to not play that good.

Both the datasets and the trained model are available.
