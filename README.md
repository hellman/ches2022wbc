# CHES 2022 - White-box Cryptography Tutorial

**Authors:** [Matthieu Rivain](https://www.matthieurivain.com/) and [Aleksei Udovenko](https://affine.group)

This repository contains preparation instructions and notebooks for the [WBC tutorial](https://ches.iacr.org/2022/affiliated.php) at CHES 2022.

## Setup (using Docker)

The simplest is to use the prepared docker image.

**WARNING**: as the image is quite large (4.5 GiB) due to SageMath, it is recommended to download it in advance:

```sh
sudo docker pull hellman1908/ches2022wbc
````
Then, run as follows:
```bash
git clone https://github.com/hellman/ches2022wbc
sudo docker run -p 127.0.0.1:9999:9999 -v `pwd`/ches2022wbc`:/home/user/ches2022wbc hellman1908/ches2022wbc
```

Alternatively, a lightweight image (without SageMath) can be installed:
```sh
sudo docker pull hellman1908/ches2022wbc_nosagemath
git clone https://github.com/hellman/ches2022wbc
sudo docker run -p 127.0.0.1:9999:9999 -v `pwd`/ches2022wbc`:/home/user/ches2022wbc hellman1908/ches2022wbc_nosagemath
```

## Setup (using Linux)

**Recommended:**

1. Install SageMath (only needed for linear algebraic attack)
2. Install pypy3 (much faster circuit gen. and attacks)

**Required:**

1. Install jupyter lab
```sh
pip install jupyterlab
```
2. Install ipykernel in each interpreter (SageMath, pypy3) until all listed in
```sh
jupyter kernelspec list
```

