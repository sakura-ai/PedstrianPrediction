import numpy as np
import tensorflow as tf

import os
import pickle
import argparse
# import ipdb

from social_lstm.DataLoader import DataLoader
from social_lstm.model import SocialLSTMModel
from social_lstm.grid import get_sequence_grid_mask, get_sequence_pyramid_mask
# from social_train import getSocialGrid, getSocialTensor


def get_mean_error(predicted_traj, true_traj, observed_length, maxNumPeds):
    '''
    Function that computes the mean euclidean distance error between the
    predicted and the true trajectory
    params:
    predicted_traj : numpy matrix with the points of the predicted trajectory
    true_traj : numpy matrix with the points of the true trajectory
    observed_length : The length of trajectory observed
    '''
    # The data structure to store all errors
    error = np.zeros(len(true_traj) - observed_length)
    # For each point in the predicted part of the trajectory
    for i in range(observed_length, len(true_traj)):
        # The predicted position. This will be a maxNumPeds x 3 matrix
        pred_pos = predicted_traj[i, :]
        # The true position. This will be a maxNumPeds x 3 matrix
        true_pos = true_traj[i, :]
        timestep_error = 0
        counter = 0
        for j in range(maxNumPeds):
            if true_pos[j, 0] == 0:
                # Non-existent ped
                continue
            elif pred_pos[j, 0] == 0:
                # Ped comes in the prediction time. Not seen in observed part
                continue
            else:
                if true_pos[j, 1] > 1 or true_pos[j, 1] < 0:
                    continue
                elif true_pos[j, 2] > 1 or true_pos[j, 2] < 0:
                    continue

                timestep_error += np.linalg.norm(true_pos[j, [1, 2]] - pred_pos[j, [1, 2]])
                counter += 1

        if counter != 0:
            error[i - observed_length] = timestep_error / counter

        # The euclidean distance is the error
        # error[i-observed_length] = np.linalg.norm(true_pos - pred_pos)

    # Return the mean error
    return np.mean(error)


def main():

    # Set random seed
    np.random.seed(1)

    parser = argparse.ArgumentParser()
    # Observed length of the trajectory parameter
    parser.add_argument('--obs_length', type=int, default=6,
                        help='Observed length of the trajectory')
    # Predicted length of the trajectory parameter
    parser.add_argument('--pred_length', type=int, default=6,
                        help='Predicted length of the trajectory')
    # Test dataset
    parser.add_argument('--test_dataset', type=int, default=3,
                        help='Dataset to be tested on')

    # Model to be loaded
    parser.add_argument('--epoch', type=int, default=49,
                        help='Epoch of model to be loaded')

    parser.add_argument("--pyramid", type=int, default=0,
                        help="whether to use pyramid method")

    # Parse the parameters
    sample_args = parser.parse_args()

    # Save directory
    save_directory = 'save/'

    # Define the path for the config file for saved args
    with open(os.path.join(save_directory, 'social_config.pkl'), 'rb') as f:
        saved_args = pickle.load(f)

    # Create a SocialModel object with the saved_args and infer set to true
    if saved_args.pyramid == 0:
        model = SocialLSTMModel(saved_args, True, pyramid=False)
    else:
        model = SocialLSTMModel(saved_args, True, pyramid=True)
    # Initialize a TensorFlow session
    sess = tf.InteractiveSession()
    # Initialize a saver
    saver = tf.train.Saver()

    # Get the checkpoint state for the model
    ckpt = tf.train.get_checkpoint_state("./save/")
    if ckpt and ckpt.model_checkpoint_path:
        saver.restore(sess, ckpt.model_checkpoint_path)

    # Dataset to get data from
    dataset = [sample_args.test_dataset]

    # Create a SocialDataLoader object with batch_size 1 and seq_length equal to observed_length + pred_length
    data_loader = DataLoader(1, sample_args.pred_length + sample_args.obs_length, saved_args.max_num_peds, force_pre_process=True, infer=False)

    # Reset all pointers of the data_loader
    data_loader.reset_batch_pointer(validate=True)

    results = []

    # Variable to maintain total error
    total_error = 0
    # For each batch
    for b in range(data_loader.num_validate_batch): # if validate: line 149 divided by 0 ??
        # Get the source, target and dataset data for the next batch
        x, y = data_loader.next_validate_batch(random_choose=False)

        # Batch size is 1
        x_batch, y_batch = x[0], y[0]

        dimensions = [640, 480]

        if saved_args.pyramid == 0:
            grid_batch = get_sequence_grid_mask(x_batch, dimensions, saved_args.neighborhood_size, saved_args.grid_size)
        else:
            grid_batch = get_sequence_pyramid_mask(x_batch)

        obs_traj = x_batch[:sample_args.obs_length]
        obs_grid = grid_batch[:sample_args.obs_length]
        # obs_traj is an array of shape obs_length x maxNumPeds x 3

        print("********************** SAMPLING A NEW TRAJECTORY", b, "******************************")
        complete_traj = model.sample(sess, obs_traj, obs_grid, dimensions, x_batch, sample_args.pred_length)

        # ipdb.set_trace()
        # complete_traj is an array of shape (obs_length+pred_length) x maxNumPeds x 3
        total_error += get_mean_error(complete_traj, x[0], sample_args.obs_length, saved_args.max_num_peds)

        print("Processed trajectory number : ", b, "out of ", data_loader.num_validate_batch, " trajectories")

        # plot_trajectories(x[0], complete_traj, sample_args.obs_length)
        # return
        results.append((x[0], complete_traj, sample_args.obs_length))

    # Print the mean error across all the batches
    print("Total mean error of the model is ", total_error/data_loader.num_validate_batch)

    print("Saving results")
    with open(os.path.join(save_directory, 'social_results.pkl'), 'wb') as f:
        pickle.dump(results, f)

if __name__ == '__main__':
    main()
