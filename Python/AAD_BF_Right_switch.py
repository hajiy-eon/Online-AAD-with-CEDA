
""""""""""""""""""""""""""""""""""""""""""
 #        OpenBCI - Brainflow           #
 #           For Online AAD              #
""""""""""""""""""""""""""""""""""""""""""


###### Imports #####
import librosa, warnings, random, time, os, sys, serial, logging, argparse, mne, scipy.io, math
import numpy as np
import matplotlib.pyplot as plt

import pandas as pd
from pylsl import StreamInlet, resolve_stream, StreamInfo
#from OpenBCI_lsl import *
from scipy import signal
from scipy.signal import butter, lfilter, resample, filtfilt
#from helper import *
from pymtrf import *
from psychopy import visual, core, event
from preprocessing_ha import *
from Comments import *
from Direction import *
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, BrainFlowError, LogLevels
from brainflow.data_filter import DataFilter, FilterTypes, AggOperations, WindowFunctions, DetrendOperations
from Brainflow_stream import *


#----------------------------- Connect to port of arduino ------------------------------#
arduino = "COM8"        # kist
#arduino = "COM10"       # hyu

port = serial.Serial(arduino, 9600)

#----------------------------- Open Brainflow network -----------------------------#
# Connect Cyton
board, args = Brainflow_stream('COM7')       # kist : COM7 / hy: COM15

# Set channels number
eeg_channels = board.get_eeg_channels(args.board_id)
aux_channels = board.get_analog_channels(args.board_id)

srate = board.get_sampling_rate(args.board_id)

#----------------------------- Load Speech segment data ------------------------------#
path = 'C:/Users/LeeJiWon/Desktop/OpenBCI'          # kist
#path = 'C:/Users/user/Desktop/hy-kist/OpenBCI'      # hyu

# Load All speech
allspeech = np.load(path + '/AAD/Python/Allspeech.npy')
# 60 by 3840  /1-30 : left by time / 31-60 righy by time // srat : 64

stim_L = allspeech[:30, :]       # 30 by 3840   // trial by time
stim_R = allspeech[30:, :]       # 30 by 3840   // trial by time

#----------------------------- Parameter Setting -----------------------------#

############## Exp parameter ################

fs = 64
tmin = 0
tmax = 250
Dir = -1
reg_lambda = 10
train = 14

##############################################

# Set int
r_L = []
r_R = []
Acc = []
ACC = []
model_w = []
inter_w = []
entr_L =[]
entr_R = []
EEG = []
AUX = []
start = []
end = []
Correct = []
Answer = []

eeg_record = np.zeros((16,1))
aux_record = np.zeros((3,1))
EEG_all = np.array([])
AUX_all = np.array([])
answer_all = np.array([])
correct_all = np.array([])

w = 1
j = 0
tr = 0

##########################
original = 'L'
opposite = 'R'
#----------------------------- Make the window for Psychopy -----------------------------#

screen = visual.Window([960, 900],
    screen = 0,
    pos = [600,0],
    fullscr = False,
    winType = 'pyglet',
    allowGUI = False,
    allowStencil = False,
    monitor ='testMonitor',
    color = [-1,-1,-1],
    blendMode = 'avg',
    units = 'pix'
    #pos = [100,0]
                    )

#------------------------------------- Warm up --------------------------------------------#
'''
tic = time.perf_counter()
toc = time.perf_counter()
while toc-tic < 30:

    input = board.get_board_data()
    eeg_data = input[eeg_channels, :]
    aux_data = input[aux_channels, :]
    print(eeg_data)

    # If Nan value is entered, restart
    if True in np.isnan(eeg_data):
        print("Input NAN")
        break

    toc = time.perf_counter()
'''

#-------------------------------------- Intro ---------------------------------------------#
file = pd.read_excel(path + "/AAD/Python/question.xlsx")
file_2 = pd.read_excel(path + "/AAD/Python/Comments.xlsx")

event.waitKeys(keyList=['space'], clearEvents=True)
Comments('intro', path, screen)


#==================================================================================================#
#-------------------------------------- START EXPERIMENT ------------------------------------------#
#==================================================================================================#

#---------- Start 30 trial ----------#

while tr < 30:   # 30

    #----------------------------- Psychopy Window & Serial Write ------------------------------#
    if w == 1:
        Direction(tr, w, original, opposite, screen, port)


    # Trigger detection
    input = board.get_board_data()
    eeg_data = input[eeg_channels, :]
    aux_data = input[aux_channels, :]
    eeg_record = np.concatenate((eeg_record, eeg_data), axis=1)
    aux_record = np.concatenate((aux_record, aux_data), axis=1)
    print(aux_data)

    #----------------------------- Trigger detection -----------------------------#
    # per trial
    if 1 in aux_data[1,:]:      # if the trigger is entered at 12 pin, start process. (include beep sound)

        print("Input Trigger {0}".format(tr+1))

        print("Start Speech")

        # Find onset point
        index = np.where(aux_record[1,:] != 0)     # Find Onset index
        onset = index[0][0]

        # Format per trial
        i = 0           # Window number
        work = 0        # Time count


    #----------------------------- Working while 60s -----------------------------#

        # onset 부터 3초 지나고 원하는 시간(한 trial) 동안 돌아가도록
        speech = onset + (srate*3) + 1   # 3초 후 부터가 speech 이기에 +1
        while i != 46:  # 46 번째 window 까지 (0~45)

            # if the processing time exceeds 1s, no time sleep
            if work > 1:
                work = 1

            # Wait 1s
            time.sleep(1 - work)

            # Time count
            start = time.perf_counter()

            ### Receive sample ###
            input = board.get_board_data()
            # Separate EEG, AUX
            eeg_data = input[eeg_channels, :]
            aux_data = input[aux_channels, :]                 # 11,12,13 / 0 or 1
            print(len(eeg_data.T))

            # Stack data
            eeg_record = np.concatenate((eeg_record, eeg_data), axis=1)     # channel by time
            aux_record = np.concatenate((aux_record, aux_data), axis=1)

            # Count time
            end = time.perf_counter()
            work = end - start


            # Stack samples until 15s and window sliding per 1s
            # After 15s, rely on time sleep.
            if len(eeg_record.T) >= (speech + (srate * 15)):

                # Adjust data as acquired from that time.
                win = eeg_record[:, speech + srate*(i) :]
                trg = aux_record[:, speech + srate*(i) :]

                if len(win.T) > srate*(15):
                    win = eeg_record[:, speech + srate*(i) : speech + srate*(15+i)]
                    print("over")

                # Check print
                print("Window number : {0}".format(i+1))
                print("Time Check : {0}s".format(len(eeg_record[:, speech:].T) / srate))


            #----------------------------- Pre-processing -----------------------------#
                # preprocessing_ha.py

                win = Preproccessing(win, srate, 0.5, 8, 3)  # data, sampling rate, low-cut, high-cut, filter order
                data_l = len(win.T)

            #------------------------------- Train set -------------------------------#
                if tr < train:  #int train
                    state = "Train set"


                    ## mTRF train function ##
                    model, tlag, inter = mtrf_train(stim_R[tr:tr+1, 64*(i):64*(i)+data_l].T, win.T, fs, Dir, tmin, tmax, reg_lambda)
                    
                    'model - (16,17,1)  / tlag - (17,1) / inter - (16,1)'

                    # Sum w - window
                    if i == 0:
                        model_w = model
                        inter_w = inter
                    else:  # i > 0 - 45까지
                        model_w = np.add(model_w, model)
                        inter_w = np.add(inter_w, inter)

                    i = i + 1
                    end = time.perf_counter()

            #------------------------------- Test set -------------------------------#
                else:
                    state = "Test set"

                    ## Calculate Predicted signal ##
                    pred, r_l, p, mse = mtrf_predict(stim_L[tr:tr+1, 64*(i):64*(i)+data_l].T, win.T, model, fs, Dir, tmin, tmax, inter)
                    pred, r_r, p, mse = mtrf_predict(stim_R[tr:tr+1, 64*(i):64*(i)+data_l].T, win.T, model, fs, Dir, tmin, tmax, inter)

                    # Stock correlation value per window(i)
                    r_L = np.append(r_L, r_l)
                    r_R = np.append(r_R, r_r)

                    ###### Estimate accuracy #####
                    if r_r > r_l:

                        acc = 1

                    else:

                        acc = 0

                    #print("acc : {0}".format(acc))

                    # Save acc for entire Accuracy
                    Acc = np.append(Acc, acc)

                    # Up window number
                    i = i + 1
                    # Time count
                    end = time.perf_counter()

                ## End one window

                # In trial 27~30, switch direction

                if tr+1 >= 27 and i > 25:
                    switching(tr, i, original, opposite, screen)

                #end = time.process_time()
                work = end - start
                print("working time = {0}s".format(work))






        #------------------------ End 60s - one trial ------------------------#
        ##### Question #####
        try :
            if tr+1 == file.TrNum[j] :
                print("Question Time")

                correct, answer = Question(j, file, path, screen)

                Correct.append(correct)
                Answer.append(answer)
                j = j+1
        except KeyError:                # 마지막 질문 후 에러나서
            pass

        # Stack eeg_record per trial & Save
        EEG.append(eeg_record.T)
        AUX.append(aux_record.T)

        ###### The things that have to calculate per trial ######
        ## Add model_w case train
        if state == "Train set":
            if tr == 0:
                model_wt = model_w
                inter_wt = inter_w
            elif tr > 0:
                model_wt = np.add(model_wt, model_w)
                inter_wt = np.add(inter_wt, inter_w)

            # Average at last train trial
            if tr == 13:
                model_wm = model_wt/(i*(tr+1))
                inter_wm = inter_wt/(i*(tr+1))
                model = model_wm
                inter = inter_wm

        elif state == "Test set":
            # Stack correlation value collected during one trial
            entr_L.append(r_L)
            entr_R.append(r_R)

            r_L = []
            r_R = []
            plt.close()

            # Collect Accuracy per trial
            ACC = np.append(ACC,np.mean(Acc))
            print("\n==================================\n")
            print("Present Accuracy = {0}%".format(ACC[-1]*100))
            print("\n==================================\n")

        # Save per trial // eeg, trigger, accuracy ,behavior
        EEG_all = np.asarray(EEG)
        AUX_all = np.asarray(AUX)
        scipy.io.savemat(path + '/save_data/E.mat', {'EEG': EEG_all})
        scipy.io.savemat(path + '/save_data/A.mat', {'AUX': AUX_all})
        scipy.io.savemat(path + '/save_data/Accuracy.mat', {'Acc': ACC})
        correct_all = np.asarray(Correct)
        scipy.io.savemat(path + '/save_data/Behavior.mat', {'Behavior': correct_all})

        #----------------------- Comments ---------------------------------#

        Comments(tr, path, screen)

        # For Next trial
        eeg_record = np.zeros((16, 1))
        aux_record = np.zeros((3, 1))

        tr = tr+1
        w = 1

#----------------------------- 30 trial End -----------------------------#
port.close()
screen.close()
board.stop_stream()
board.release_session()
print("The End")


#### save ####
# mat save
answer_all = np.asarray(Answer)
scipy.io.savemat(path + '/save_data/Answer.mat', {'Answer': answer_all})

# np save
np.save(path+'/save_data/EEG', EEG_all)
np.save(path+'/save_data/A', AUX_all)
np.save(path+'/save_data/All_Accuracy', ACC)
entr_L = np.asarray(entr_L)
entr_R = np.asarray(entr_R)
np.save(path+'/save_data/All_correlation_right', entr_R)
np.save(path+'/save_data/All_correlation_left', entr_L )

                            
