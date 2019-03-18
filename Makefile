sdist:
	python3 setup.py sdist

signed-rpm: sdist
	rpmbuild -ba imagefactory.spec --sign --define "_sourcedir `pwd`/dist"

rpm: sdist
	rpmbuild -ba imagefactory.spec --define "_sourcedir `pwd`/dist"

srpm: sdist
	rpmbuild -bs imagefactory.spec --define "_sourcedir `pwd`/dist"

pylint:
	pylint --rcfile=pylint.conf imagefactory imgfac

unittests:
	python3 -m unittest discover -v

clean:
	rm -rf MANIFEST build dist imagefactory.spec
