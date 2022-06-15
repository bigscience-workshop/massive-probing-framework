from transformers import  AutoConfig, AutoModel, AutoTokenizer
import torch
import logging
from typing import Optional, List, Tuple, Union, Dict
from enum import Enum

from probing.utils import exclude_rows


class TransformersLoader:
    def __init__(
        self,
        model_name: Enum,
        device: Optional[Enum] = None,
        truncation: bool = False,
        padding: Enum = "longest",
        return_tensors: Enum = "pt",
        add_special_tokens: bool = True,
        return_dict: bool = True,
        output_hidden_states: bool = True,
        output_attentions: bool = True,
        max_length: int = 512
    ):
        self.config = AutoConfig.from_pretrained(
            model_name, output_hidden_states=output_hidden_states, 
            output_attentions=output_attentions
            )
        self.model = AutoModel.from_pretrained(
            model_name, config=self.config
            )
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, config=self.config
            )

        self.truncation = truncation 
        self.padding = padding
        self.return_tensors = return_tensors
        self.add_special_tokens = add_special_tokens
        self.return_dict = return_dict
        self.max_length = max_length

        if device:
            self.device = device
            self.model.to(torch.device(self.device))
        elif torch.cuda.is_available():
            self.model.cuda()
            self.device = self.model.device
        else:
            self.device = "cpu"
            self.model.to(torch.device(self.device))

    def _get_output_tensors(self, encoded_text: Dict[str, torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor, List[int]]:
        input_ids = encoded_text["input_ids"]
        attention_mask = encoded_text["attention_mask"]
        row_ids_to_exclude = []
        if not self.truncation and input_ids.size()[1] > self.max_length:
            pad_token_id = self.tokenizer.pad_token_id
            row_ids_to_exclude = torch.where(input_ids[:, self.max_length - 1] > pad_token_id)

            input_ids = exclude_rows(input_ids, row_ids_to_exclude)[:, :self.max_length]
            attention_mask = exclude_rows(attention_mask, row_ids_to_exclude)[:, :self.max_length]

        if row_ids_to_exclude:
            logging.warning(f"Since you decided not to truncate long sentences, {len(row_ids_to_exclude)} samples were excluded.")
        return input_ids.to(self.device), attention_mask.to(self.device), row_ids_to_exclude

    def _get_embeddings_by_layers(self, model_outputs: Tuple[torch.Tensor], embedding_type: Enum):
        layers_outputs = []
        for output in model_outputs[1:]:
            if embedding_type == 'cls':
                sent_vector = output[:, 0, :]
            elif embedding_type == 'sum':
                sent_vector = torch.sum(output, dim=1)
            elif embedding_type == 'avg':
                sent_vector = torch.mean(output, dim=1)
            else:
                raise NotImplementedError(
                    f'Unknown type of embedding\'s aggregation: {embedding_type}'
                    )
            layers_outputs.append(sent_vector.cpu())
        return layers_outputs

    def encode_text(
        self,
        text: Union[str, List[str]],
        embedding_type: Enum = 'cls'
    ) -> Tuple[List[torch.Tensor], List[int]]:
        encoded_text = self.tokenizer(
            text,
            padding=self.padding,
            return_tensors=self.return_tensors,
            add_special_tokens = self.add_special_tokens,
            max_length = self.max_length,
            truncation = self.truncation
        )
        input_ids, attention_mask, row_ids_to_exclude = self._get_output_tensors(encoded_text)
        with torch.no_grad():
            model_outputs = self.model(
                    input_ids, attention_mask, return_dict=self.return_dict
            )
            model_outputs = (
                model_outputs["hidden_states"]
                if "hidden_states" in model_outputs
                else model_outputs["encoder_hidden_states"]
            )
            layers_outputs = self._get_embeddings_by_layers(model_outputs, embedding_type)
            return layers_outputs, row_ids_to_exclude
