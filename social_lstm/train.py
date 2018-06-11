import tensorflow as tf
import argparse
from social_lstm.DataLoader import DataLoader
from social_lstm.model import SocialLSTMModel
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lstm_num", type=int, default=128,
                        help="size of lstm hidden state")
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--seq_length", type=int, default=12,
                        help="RNN sequence length")
    parser.add_argument("--num_epochs", type=int, default=50)
    parser.add_argument("--save_freq", type=int, default=400,
                        help="save every")
    parser.add_argument('--gradient_clip', type=float, default=10.,
                        help='clip gradients at this value')
    parser.add_argument('--learning_rate', type=float, default=0.005,
                        help='learning rate')
    parser.add_argument('--decay_rate', type=float, default=0.95,
                        help='decay rate for rmsprop')
    parser.add_argument('--embedding_size', type=int, default=64,
                        help='Embedding dimension for the spatial coordinates')
    parser.add_argument('--neighborhood_size', type=int, default=32,
                        help='Neighborhood size to be considered for social pooling')
    parser.add_argument('--grid_size', type=int, default=4,
                        help='Grid size of the social pooling')
    parser.add_argument('--max_num_peds', type=int, default=40,
                        help='Maximum Number of Pedestrians')
    parser.add_argument('--L2_param', type=float, default=0.0005,
                        help='L2 regularization parameter')
    args = parser.parse_args()
    train(args)


def train(args):
    data_loader = DataLoader(args.batch_size,
                             args.seq_lengths,
                             args.max_num_peds,
                             force_pre_process=True,
                             infer=False)
    model = SocialLSTMModel(args)
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    with tf.Session() as sess:
        sess.run(tf.initialize_all_variables())
        saver = tf.train.Saver(tf.all_variables)
        best_validate_loss = 100
        best_epoch = 0

        # For each epoch
        for e in range(args.num_epochs):
            # Assign the learning rate value for this epoch
            sess.run(tf.assign(model.lr, args.learning_rate * (args.decay_rate ** e)))
            # Reset the data pointers in the data_loader
            data_loader.reset_batch_pointer(validate=False)

            loss_epoch = 0

            # For each batch
            for b in range(data_loader.num_training_batch):
                # Tic
                start = time.time()

                # Get the source, target and dataset data for the next batch
                # x, y are input and target data which are lists containing numpy arrays of size seq_length x maxNumPeds x 3
                x, y = data_loader.next_training_batch()

                # variable to store the loss for this batch
                loss_batch = 0

                # For each sequence in the batch
                for batch in range(data_loader.batch_size):
                    # x_batch, y_batch and d_batch contains the source, target and dataset index data for
                    # seq_length long consecutive frames in the dataset
                    # x_batch, y_batch would be numpy arrays of size seq_length x maxNumPeds x 3
                    # d_batch would be a scalar identifying the dataset from which this sequence is extracted
                    x_batch, y_batch = x[batch], y[batch]

                    dataset_data = [640, 480]

                    grid_batch = getSequenceGridMask(x_batch, dataset_data, args.neighborhood_size, args.grid_size)

                    # Feed the source, target data
                    feed = {model.input_data: x_batch, model.target_data: y_batch, model.grid_data: grid_batch}

                    train_loss, _ = sess.run([model.cost, model.train_op], feed)

                    loss_batch += train_loss

                end = time.time()
                loss_batch = loss_batch / data_loader.batch_size
                loss_epoch += loss_batch
                print(
                    "{}/{} (epoch {}), train_loss = {:.3f}, time/batch = {:.3f}"
                        .format(
                        e * data_loader.num_batches + b,
                        args.num_epochs * data_loader.num_batches,
                        e,
                        loss_batch, end - start))

                # Save the model if the current epoch and batch number match the frequency
                '''
                if (e * data_loader.num_batches + b) % args.save_every == 0 and ((e * data_loader.num_batches + b) > 0):
                    checkpoint_path = os.path.join('save', 'social_model.ckpt')
                    saver.save(sess, checkpoint_path, global_step=e * data_loader.num_batches + b)
                    print("model saved to {}".format(checkpoint_path))
                '''
            loss_epoch /= data_loader.num_batches
            log_file_curve.write(str(e) + ',' + str(loss_epoch) + ',')
            print
            '*****************'

            # Validation
            data_loader.reset_batch_pointer(valid=True)
            loss_epoch = 0

            for b in range(data_loader.num_batches):

                # Get the source, target and dataset data for the next batch
                # x, y are input and target data which are lists containing numpy arrays of size seq_length x maxNumPeds x 3
                # d is the list of dataset indices from which each batch is generated (used to differentiate between datasets)
                x, y, d = data_loader.next_valid_batch()

                # variable to store the loss for this batch
                loss_batch = 0

                # For each sequence in the batch
                for batch in range(data_loader.batch_size):
                    # x_batch, y_batch and d_batch contains the source, target and dataset index data for
                    # seq_length long consecutive frames in the dataset
                    # x_batch, y_batch would be numpy arrays of size seq_length x maxNumPeds x 3
                    # d_batch would be a scalar identifying the dataset from which this sequence is extracted
                    x_batch, y_batch, d_batch = x[batch], y[batch], d[batch]

                    if d_batch == 0 and datasets[0] == 0:
                        dataset_data = [640, 480]
                    else:
                        dataset_data = [720, 576]

                    grid_batch = getSequenceGridMask(x_batch, dataset_data, args.neighborhood_size, args.grid_size)

                    # Feed the source, target data
                    feed = {model.input_data: x_batch, model.target_data: y_batch, model.grid_data: grid_batch}

                    train_loss = sess.run(model.cost, feed)

                    loss_batch += train_loss

                loss_batch = loss_batch / data_loader.batch_size
                loss_epoch += loss_batch

            loss_epoch /= data_loader.valid_num_batches

            # Update best validation loss until now
            if loss_epoch < best_val_loss:
                best_val_loss = loss_epoch
                best_epoch = e

            print('(epoch {}), valid_loss = {:.3f}'.format(e, loss_epoch))
            print
            'Best epoch', best_epoch, 'Best validation loss', best_val_loss
            log_file_curve.write(str(loss_epoch) + '\n')
            print
            '*****************'

            # Save the model after each epoch
            print
            'Saving model'
            checkpoint_path = os.path.join(save_directory, 'social_model.ckpt')
            saver.save(sess, checkpoint_path, global_step=e)
            print("model saved to {}".format(checkpoint_path))


if __name__ == "__main__":
    main()
