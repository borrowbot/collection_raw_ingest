import requests
import praw
from datetime import datetime
from dateutil.relativedelta import relativedelta

import collection_reddit_raw.src.psraw as psraw
from lib_borrowbot_core.raw_objects.submission import Submission
from lib_borrowbot_core.raw_objects.comment import Comment
from lib_borrowbot_core.raw_objects.user import User
from collection_reddit_raw.src.writers.submission_writer import SubmissionWriter
from collection_reddit_raw.src.writers.comment_writer import CommentWriter
from collection_reddit_raw.src.writers.user_lookup_writer import UserLookupWriter


class RedditRawTask(object):
    def __init__(self, logger, subreddit, sql_params, reddit_params, cutoff_months=6):
        self.sql_params = sql_params
        self.subreddit = subreddit
        self.logger = logger
        self.reddit_params = reddit_params
        self.sql_params = sql_params
        self.cutoff_months = cutoff_months

        self.reddit = praw.Reddit(**self.reddit_params)
        self.comment_writer = CommentWriter(logger, sql_params, float('inf'))
        self.submission_writer = SubmissionWriter(logger, sql_params, float('inf'))
        self.user_lookup_writer = UserLookupWriter(logger, sql_params, float('inf'))


    def main(self, block):
        assert 'limit' in block
        assert 'after' in block
        cutoff_time = datetime.utcnow() + relativedelta(months=-self.cutoff_months)

        iterator = psraw.submission_search(
            self.reddit, q='', subreddit=self.subreddit,
            limit=block['limit'], sort='asc', after=block['after']
        )

        for submission in iterator:
            self.logger.info("{}: {}".format(
                datetime.fromtimestamp(submission.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                submission.permalink
            ))
            s = Submission(init_object=submission)
            if s.creation_datetime > cutoff_time:
                break
            u = User(user_id=s.author_id, user_name=s.author_name)
            self.submission_writer.push(s)
            if u.user_id is not None and u.user_name is not None:
                self.user_lookup_writer.push(u)

            comment_iterator = psraw.comment_search(
                self.reddit, q='', subreddit=self.subreddit, limit=100000,
                sort='asc', link_id=submission.id
            )

            for comment in comment_iterator:
                self.logger.info(" | {}".format(
                    datetime.fromtimestamp(comment.created_utc).strftime('%Y-%m-%d %H:%M:%S')
                ))
                self.comment_writer.push(Comment(init_object=comment))

        self.submission_writer.flush()
        self.comment_writer.flush()
        self.user_lookup_writer.flush()
