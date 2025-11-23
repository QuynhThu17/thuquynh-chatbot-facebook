from controllers.llm import token as _token
from configs import constant

import logging
logger = logging.getLogger(__name__)


def context_reduce(contexts, model):
    num_token_input = 0
    count_white = 0

    while True:
        try:
            num_token = _token.calculate_tokens(str(contexts), model, name="context_reduce")
            num_token_input = num_token

            if num_token < constant.MAX_NUM_TOKEN:
                break

            count_tmp = 5000

            if num_token > constant.MAX_NUM_TOKEN:
                count_tmp = num_token - constant.MAX_NUM_TOKEN
                if count_tmp < 5000:
                    count_tmp = 5000
            contexts = contexts[:-count_tmp]

            count_white += 1
            if count_white > 15:
                break

        except Exception as e:
            logger.error(f"Error in get_num_tokens: {e}")
            break

    return contexts, num_token_input
