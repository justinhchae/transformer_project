from src import utils, bert_sequence
from src.bert_sequence.train_epoch import train_epoch
from src.bert_sequence.test_epoch import test_epoch

import torch
from transformers import get_linear_schedule_with_warmup

from functools import partial
from transformers import AdamW
from pprint import pprint
import numpy as np
import time
import random
import progressbar


def network(device, use_seed=False, torch_corpora_name="ag_news", do_break_testing=False):
    if use_seed:
        random.seed(utils.constants.SEED_VAL)
        np.random.seed(utils.constants.SEED_VAL)
        torch.manual_seed(utils.constants.SEED_VAL)
        torch.cuda.manual_seed_all(utils.constants.SEED_VAL)

    # TODO: structure/package network and training parameters
    bert_name = 'bert'
    bert_case_type = 'uncased'
    bert_type = f"{bert_name}-base-{bert_case_type}"
    bert_variation = "modelForSequenceClassification"
    batch_size = 8
    tensor_type = "pt"
    shuffle_dataloader = True
    epochs = 1
    learning_rate = 5e-5

    # make a tokenizer from HF library
    tokenizer = utils.make_tokenizer(bert_name, bert_case_type)

    data = utils.data.get_corpora(torch_corpora_name=torch_corpora_name, tokenizer=tokenizer, batch_size=batch_size
                                  , shuffle_dataloader=shuffle_dataloader, tensor_type=tensor_type)

    train_loader = data['train_loader']
    test_loader = data['test_loader']
    # TODO: allow test/validation split from a single test set
    if "valid_loader" in data.keys():
        valid_loader = data['valid_loader']
    else:
        valid_loader = None

    num_labels = data['num_labels']

    # check how the encoder/decoder works on a single input after encoding and batching
    utils.data.demo_encoder_decoder(train_loader, tokenizer, torch_corpora_name=torch_corpora_name)
    # see what the labels are
    print("=" * 40, f'The Labels for {torch_corpora_name} are {data["labels_list"]}')

    model = bert_sequence.model.Model(num_labels=num_labels, bert_type=bert_type)
    model.to(device)

    optim = AdamW(model.parameters(), lr=learning_rate)

    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(optimizer=optim
                                                , num_warmup_steps=0
                                                , num_training_steps=total_steps)

    # validation accuracy, and timings
    training_stats = []
    curr_step = 0
    total_t0 = time.time()

    print("=" * 10, f'Starting Training for {torch_corpora_name}', "=" * 10, "\n")

    with progressbar.ProgressBar(max_value=total_steps) as progress:

        for epoch_i in range(0, epochs):
            t0 = time.time()
            # run the train loop
            avg_train_loss, curr_step = train_epoch(model, train_loader, optim, progress, scheduler, curr_step, device
                                                    , break_test=do_break_testing)
            print("")
            print("=" * 20, f"Epoch: {epoch_i + 1} | Corpora: {torch_corpora_name}", "=" * 20)
            print("  Average training loss: {0:.2f}".format(avg_train_loss))
            # run the test loop
            avg_test_accuracy, avg_test_loss = test_epoch(model, test_loader, device, break_test=do_break_testing)
            print("  Test Loss: {0:.2f}".format(avg_test_loss))
            print("  Test Accuracy: {0:.2f}".format(avg_test_accuracy))
            print("=" * 20)
            epoch_time = utils.train_helpers.format_time(time.time() - t0)

            training_stats.append(
                {
                    'Corpora': torch_corpora_name,
                    'Epoch': epoch_i + 1,
                    'Training Loss': avg_train_loss,
                    'Test Loss': avg_test_loss,
                    'Test Accuracy': avg_test_accuracy,
                    'Epoch Time': epoch_time,
                    'Number of Classes': num_labels,
                    'Batch Size': batch_size,
                    'Bert Model': bert_variation,
                    'Bert Type': bert_type,

                }
            )

    print("")
    print("Training complete!")

    print("Total training took {:} (h:mm:ss)".format(utils.train_helpers.format_time(time.time() - total_t0)))
    pprint(training_stats)
    print("=" * 40, "\n")

    model_save = utils.data.save_model(model, f"{torch_corpora_name}_{bert_name}")
    print(f"Saving model state dict to {model_save}")
    return training_stats
