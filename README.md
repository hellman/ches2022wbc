# CHES 2022 - White-box Cryptography Tutorial

**Authors:** [Matthieu Rivain](https://www.matthieurivain.com/) and [Aleksei Udovenko](https://affine.group)

This repository contains preparation instructions and notebooks for the [WBC tutorial](https://ches.iacr.org/2022/affiliated.php) at CHES 2022.

**Note:** the repository is currently assembled primarily for the tutorial at CHES 2022; a large part of the tutorial should be runnable with just `pip install circkit wboxkit` and the jupyter lab / notebook. However, some parts (e.g. wboxkit.fastcircuit compilation) are not yet automatically built when installing from pip (will be fixed soon).

The main repository for `circkit` is: [github.com/cryptoexperts/circkit](https://github.com/cryptoexperts/circkit)
The tutorial was prepared using a local copy of `circkit` in this repository, but `pip install circkit` should also work.


## Minimal Setup (pure Python)

Might be slow and LDA won't work.

```bash
sudo apt install graphviz

pip install jupyterlab binteger pycryptodome graphviz
```

Running notebooks:

```sh
jupyter lab
```

Running tools/attacks:

```sh
export PYTHONPATH=.:$PYTHONPATH
python3 tools/trace.py ...
python3 attacks/analyze_exact.py ....
```


## Setup (using Docker)

The simplest is to use the prepared docker image.

**WARNING**: as the image is quite large (4.5 GiB) due to SageMath, it is recommended to download it in advance:

```bash
sudo docker pull hellman1908/ches2022wbc
```
Then, run as follows:
```bash
git clone https://github.com/hellman/ches2022wbc

# run Jupyter Notebook
sudo docker run -it \
	--network=host \
	-v `pwd`/ches2022wbc:/home/user/ches2022wbc \
	hellman1908/ches2022wbc

# run shell
sudo docker run -it \
	--network=host \
	-v `pwd`/ches2022wbc:/home/user/ches2022wbc \
	hellman1908/ches2022wbc /bin/bash
```

Then, Ctrl+Click or copy/paste the link `http://127.0.0.1:9999/lab?token=...`.

Alternatively, a lightweight image (without SageMath) can be installed:
```bash
sudo docker pull hellman1908/ches2022wbc_nosagemath
git clone https://github.com/hellman/ches2022wbc
sudo docker run -it \
	--network=host \
	-v `pwd`/ches2022wbc:/home/user/ches2022wbc \
	hellman1908/ches2022wbc_nosagemath
```

Note: without host network, try running
```bash
sudo docker run -it \
	-p 127.0.0.1:9999:9999 \
	-v `pwd`/ches2022wbc:/home/user/ches2022wbc \
	hellman1908/ches2022wbc_nosagemath \
	jupyter lab --no-browser --port=9999 --ip=127.0.0.1
```


## Setup (using Linux)

**Recommended:**

1. Install [SageMath](https://doc.sagemath.org/html/en/installation/index.html) (only needed for linear algebraic attack)
2. Install [pypy3](https://www.pypy.org/download.html) (much faster circuit gen. and attacks)

**Required:**

1. Install jupyter lab (any python env.)
```bash
pip install jupyterlab
```
2. Install `ipykernel` for the `pypy3` interpreter, e.g.:
```bash
pypy3 -m pip install -U pip
pypy3 -m pip install -U pycryptodome binteger ipykernel jupyter_client
pypy3 -m ipykernel install --prefix=$HOME/.local/ --name 'pypy3'

jupyter kernelspec list
```
3. Clone this repository and compile the fastcircuit library:
```bash
git clone https://github.com/hellman/ches2022wbc
cd ches2022wbc
make
````
3. Test running jupyter as
```bash
jupyter lab
```
Then, Ctrl+Click or copy/paste the link `http://127.0.0.1:9999/lab?token=...`.

You can also try opening the `Tutorial 0 - Test Setup.ipynb` in the ches2022wbc repository, and executing the code cell.