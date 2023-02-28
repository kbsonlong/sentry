"""
Aliyun OSS filestore

sentry config.yaml:
==========
filestore.backend: 'oss'
filestore.options:
  access_key: 'AKIXXXXXX'
  secret_key: 'XXXXXXX'
  bucket_name: 'osss-bucket-name'
  endpoint_url:  'oss-cn-shenzhen.aliyuncs.com'
  log_file: '/data/service/oss_log/oss.log'
  host_location: '/tmp/sentry-files'
==========
log_file  独立输出 oss DEBUG日志，不配置不开启
host_location  本地 sourceMap 存储位置。读取时先尝试本地，再走oss

change logs:
# TODO: 阿里云oss 存储策略：转低频，过期删除(100%）
# TODO：阿里云oss 读取判断存储类型，如归档存储，转换为低频存储（转换有1分钟时间窗口，暂不处理）
# TODO: 减少阿里云连接，和auth创建 (auth 需要继承分析过期，暂缓）
# TODO：路径前缀、用于划分目录（100%）
# TODO:下载校验crc64（默认是开启crc，需要下载时对比 client server crc）（100%）
# TODO:支持本地文件读取，优雅灰度(100%)
"""

from __future__ import absolute_import

import logging
import os
import posixpath

import oss2
from django.core.files.base import File
from django.core.files.storage import Storage
from django.utils.encoding import force_bytes, force_text, smart_str
from django.utils.six import BytesIO
from oss2 import Bucket, ObjectIterator, Session
from oss2.auth import Auth
from oss2.exceptions import ClientError, RequestError, ServerError
from oss2.models import BucketLifecycle, LifecycleExpiration, LifecycleRule, StorageTransition
from oss2.utils import Crc64

from sentry import options
from sentry.utils import metrics

# 支持utf-8
# import sys


# reload(sys)
# sys.setdefaultencoding("utf-8")
##

logger = logging

if options.get("filestore.backend") == "oss" and options.get("filestore.options").get("log_file"):
    log_file_path = options.get("filestore.options").get("log_file", "oss.log")
    oss2.set_file_logger(log_file_path, "oss2", logging.DEBUG)
    logger = oss2.logger
else:
    logger = logging.getLogger(__name__)

OSS_RETRIES = 3

_SESSION = Session()
_AUTH = None

storage_prefix = options.get("filestore.options", {}).get("file_prefix", "") or "sentry"


def _get_session():
    return _SESSION


def safe_join(base, *paths):
    """
    A version of django.utils._os.safe_join for S3 paths.
    Joins one or more path components to the base path component
    intelligently. Returns a normalized version of the final path.
    The final path must be located inside of the base path component
    (otherwise a ValueError is raised).
    Paths outside the base path indicate a possible security
    sensitive operation.
    """
    base_path = force_text(base)
    base_path = base_path.rstrip("/")
    paths = [force_text(p) for p in paths]
    final_path = base_path + "/"
    for path in paths:
        _final_path = posixpath.normpath(posixpath.join(final_path, path))
        # posixpath.normpath() strips the trailing /. Add it back.
        if path.endswith("/") or _final_path + "/" == final_path:
            _final_path += "/"
        final_path = _final_path
    if final_path == base_path:
        final_path += "/"

    # Ensure final_path starts with base_path and that the next character after
    # the base path is /.
    base_path_len = len(base_path)
    if not final_path.startswith(base_path) or final_path[base_path_len] != "/":
        raise ValueError("the joined path is located outside of the base path" " component")

    return final_path.lstrip("/")


def clean_name(name):
    """
    Cleans the name so that Windows style paths work
    """
    # Normalize Windows style paths
    clean_name = posixpath.normpath(name).replace("\\", "/")

    # os.path.normpath() can strip trailing slashes so we implement
    # a workaround here.
    if name.endswith("/") and not clean_name.endswith("/"):
        # Add a trailing slash as it was stripped.
        clean_name = clean_name + "/"

    # Given an empty string, os.path.normpath() will return ., which we don't want
    if clean_name == ".":
        clean_name = ""

    return clean_name


def try_repeated(func):
    """
    Runs a function a few times ignoring errors we see from GCS
    due to what appears to be network issues.  This is a temporary workaround
    until we can find the root cause.
    """
    if hasattr(func, "__name__"):
        func_name = func.__name__
    elif hasattr(func, "func"):
        # Partials
        func_name = getattr(func.func, "__name__", "__unknown__")
    else:
        func_name = "__unknown__"

    metrics_key = "filestore.oss.retry"
    metrics_tags = {"function": func_name}
    idx = 0
    while True:
        try:
            result = func()
            metrics_tags.update({"success": "1"})
            metrics.timing(metrics_key, idx, tags=metrics_tags)
            return result
        except (ClientError, RequestError, ServerError) as e:
            if idx >= OSS_RETRIES:
                metrics_tags.update({"success": "0", "exception_class": e.__class__.__name__})
                metrics.timing(metrics_key, idx, tags=metrics_tags)
                raise
        idx += 1


def _set_lifecycle_rule():
    # 设置存储类型转换规则，
    # 指定Object在其最后修改时间20天之后转为低频访问类型，在其最后修改时间90天之后转为归档类型。
    # 设置object距其最后修改时间365天后过期。
    ak = options.get("filestore.options").get("access_key")
    sk = options.get("filestore.options").get("secret_key")
    bucket_name = options.get("filestore.options").get("bucket_name")
    endpoint_url = options.get("filestore.options").get("endpoint_url")

    auth = Auth(ak, sk)
    rule = LifecycleRule(
        "rule1",
        storage_prefix + "/",
        status=LifecycleRule.ENABLED,
        storage_transitions=[
            StorageTransition(days=20, storage_class=oss2.BUCKET_STORAGE_CLASS_IA),
            StorageTransition(days=90, storage_class=oss2.BUCKET_STORAGE_CLASS_ARCHIVE),
        ],
        expiration=LifecycleExpiration(days=365),
    )
    lifecycle = BucketLifecycle([rule])
    Bucket(auth, endpoint_url, bucket_name).put_bucket_lifecycle(lifecycle)


def _cover_prefix_name(name):
    """
    文件读写是增加前缀，用于对象存储模拟目录
    """
    global storage_prefix
    return storage_prefix.strip().rstrip("/") + "/" + name


class AliyunOssFile(File):
    # 默认上传存储类型低频文档，降低费用
    # 取值：Standard、IA、Archive、ColdArchive
    # 含义：标准、低频、归档、冷归档
    default_storage_class = "IA"

    def __init__(self, name, mode, storage):
        logger.debug("create oss file:" + name)
        self._storage = storage
        self._name = name
        self._mode = mode
        self._file = None
        self.obj = None
        self._is_dirty = False
        self._size = 0
        self._set_lifecycle_rule = _set_lifecycle_rule()

    @property
    def size(self):
        return self._size

    def _get_file(self):
        if self._file is None:
            with metrics.timer("filestore.read", instance="oss"):
                self._file = BytesIO()
                if "r" in self._mode:
                    self._is_dirty = False
                    data, size = self._storage.get_object(self._name)
                    self._size = size
                    self._file.write(data)
                    self._file.seek(0)
        return self._file

    def _set_file(self, value):
        self._file = value

    file = property(_get_file, _set_file)

    def read(self, *args, **kwargs):
        if "r" not in self._mode:
            raise AttributeError("File was not opened in read mode.")
        return super().read(*args, **kwargs)

    def write(self, content):
        if "w" not in self._mode:
            raise AttributeError("File was not opened in write mode.")
        self._is_dirty = True
        headers = dict()
        headers["x-oss-storage-class"] = self.default_storage_class
        self._storage.bucket.put_object(_cover_prefix_name(self._name), content, headers=headers)
        # self._storage.bucket.put_bucket_lifecycle()
        return super().write(force_bytes(content))

    def close(self):
        # if self._is_dirty:
        #     self._flush_write_buffer()
        #     # TODO: Possibly cache the part ids as they're being uploaded
        #     # instead of requesting parts from server. For now, emulating
        #     # s3boto's behavior.
        #     parts = [
        #         {
        #             'ETag': part.e_tag,
        #             'PartNumber': part.part_number
        #         } for part in self._multipart.parts.all()
        #     ]
        #     self._multipart.complete(MultipartUpload={'Parts': parts})
        # else:
        #     if self._multipart is not None:
        #         self._multipart.abort()
        if self._file is not None:
            logger.debug("close oss file handler:" + self._name)
            self._file.close()
            self._file = None


class AliyunOssStorage(Storage):
    endpoint_url = ""
    bucket_name = ""
    access_key = ""
    secret_key = ""
    file_name_charset = "utf-8"
    key_prefix = "sentry"
    host_location = ""

    def __init__(self, **settings):
        for k, v in settings.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self._bucket = None
        self._auth = None

    @property
    def auth(self):
        if not self._auth:
            self._auth = Auth(self.access_key, self.secret_key)
        return self._auth

    @property
    def bucket(self):
        if not self._bucket:
            self._bucket = Bucket(
                self.auth, self.endpoint_url, self.bucket_name, session=_get_session()
            )
        return self._bucket

    def _normalize_name(self, name):
        """
        Normalizes the name so that paths like /path/to/ignored/../something.txt
        and ./file.txt work.  Note that clean_name adds ./ to some paths so
        they need to be fixed here.
        """
        return safe_join("", name)

    def _encode_name(self, name):
        return smart_str(name, encoding=self.file_name_charset)

    def _open(self, name, mode="rb"):
        logger.debug("oss open:" + name)
        name = self._normalize_name(clean_name(name))
        return AliyunOssFile(name, mode, self)

    def _save(self, name, content):
        def _try_upload():
            content.seek(0, os.SEEK_SET)
            o_file.write(content)

        logger.debug("oss save:" + name)
        with metrics.timer("filestore.save", instance="gcs"):
            cleaned_name = clean_name(name)
            name = self._normalize_name(cleaned_name)
            content.name = cleaned_name
            encoded_name = self._encode_name(name)
            o_file = AliyunOssFile(encoded_name, "w", self)
            try_repeated(_try_upload)
        return cleaned_name

    def delete(self, name):
        name = self._normalize_name(clean_name(name))
        logger.debug("delete storage file:" + name)
        if not self.host_location:
            self.bucket.delete_object(name)
        else:
            local_path = os.path.join(self.host_location, name)
            if os.path.exists(local_path):
                os.remove(local_path)

    def exists(self, name):
        name = self._normalize_name(clean_name(name))
        if not self.host_location:
            return self.bucket.object_exists(name)
        else:
            local_path = os.path.join(self.host_location, name)
        return os.path.exists(local_path)

    def listdir(self, path):
        dir_list = []
        for obj in ObjectIterator(self.bucket, prefix=path, delimiter="/"):
            kind = "d" if obj.is_prefix() else "f"
            dir_list.append([obj.key, kind])
        return dir_list

    def size(self, name):
        name = self._normalize_name(clean_name(name))
        logger.debug("get storage file size:" + name)
        if not self.host_location:
            return self.bucket.get_object_meta(name).headers["Size"]
        else:
            local_path = os.path.join(self.host_location, name)
        return os.path.getsize(local_path) if os.path.exists(local_path) else 0

    def url(self, name):
        pass

    def get_object(self, name):
        """
        读取存储文件内容
        支持本地存储，用于切到 oss，本地文件未上传内容读取
        :param name: 文件名，或者oss key
        :return:
            content 文件内容
            size    文件大小
        """
        name = self._normalize_name(clean_name(name))
        # 本地存储读取
        if self.host_location:
            local_path = os.path.join(self.host_location, name)
            logger.debug("get object content from local file:" + local_path)
            if os.path.exists(local_path):
                size = os.path.getsize(local_path)
                with open(local_path) as f:
                    return f.read(), size

        # oss 读取
        name = _cover_prefix_name(name)
        logger.debug("get object content from oss:" + name)
        obj_stream = self.bucket.get_object(name)
        content = obj_stream.read()
        size = obj_stream.content_length
        server_crc = obj_stream.server_crc
        obj_stream.close()
        client_crc = Crc64()
        client_crc.update(content)
        logger.debug("client crc:" + str(client_crc.crc))
        logger.debug("server crc:" + str(server_crc))
        if self.bucket.enable_crc and client_crc.crc != server_crc:
            raise Exception("The CRC checksum between client and server is inconsistent!")
        return content, size
