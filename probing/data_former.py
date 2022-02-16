from enum import Enum
from typing import Tuple, Dict, Optional, List, Union
import os
import numpy as np
from tqdm import tqdm

from utils import get_probe_task_path

from torch.utils.data import DataLoader
from torch.utils.data import BatchSampler


class DataFormer:
    def __init__(
        self,
        probe_task: Enum,
        data_path: Optional[os.PathLike] = None
    ):
        self.probe_task = probe_task
        self.data_path = get_probe_task_path(probe_task, data_path)

        self.samples = self.__form_data()

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]

    def __form_data(self) -> Dict[Enum, Tuple[Enum, str]]:
        samples_dict = {}
        f = open(self.data_path)
        for line in list(f):
            data_type, label, text = line.strip().split("\t")
            if data_type not in samples_dict:
                samples_dict[data_type] = []
            samples_dict[data_type].append((text, label))
        return samples_dict


class EncodeLoader:
    def __init__(
        self,
        list_texts_labels: List[Tuple[str, Enum]],
        encode_func,
        batch_size: int=128,
        drop_last: bool=False,
        shuffle: bool=False
    ):  
        self.encode_func = encode_func
        self.list_texts_labels = list_texts_labels
        self.batch_size = batch_size
        self.drop_last = drop_last
        self.shuffle = shuffle
        
        self.dataset = self.__form_dataloader()
    
    def __len__(self):
        return len(self.dataset)

    def __form_dataloader(self) -> DataLoader:
        sampled_texts, sampled_labels = self.__get_sampled_data()
        dataset = []
        for batch_text, batch_label in tqdm(
            zip(sampled_texts, sampled_labels), 
            total = len(sampled_texts),
            desc='Data encoding'
        ):
            dataset.append((self.encode_func(batch_text), batch_label))

        return DataLoader(
            dataset=dataset,
            shuffle=self.shuffle
        ) 
    
    def __get_sampled_data(self) -> Tuple[List[str], List[Union[Enum, int]]]:
        texts, labels = [], []
        for sample in self.list_texts_labels:
            texts.append(sample[0])
            labels.append(sample[1])

        sampled_texts = self.__batch_sampler(texts)
        sampled_labels = self.__batch_sampler(labels)
        return sampled_texts, sampled_labels
    
    def __batch_sampler(self, list_data)->BatchSampler:
        return BatchSampler(
            list_data,
            batch_size = self.batch_size,
            drop_last = self.drop_last
        )
