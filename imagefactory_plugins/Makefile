sdist:
	python setup.py sdist

signed-rpm: sdist
	rpmbuild -ba imagefactory-plugins.spec --sign --define "_sourcedir `pwd`/dist"

rpm: sdist
	rpmbuild -ba imagefactory-plugins.spec --define "build_mock 1" --define "_sourcedir `pwd`/dist"

rpmnomock: sdist
	rpmbuild -ba imagefactory-plugins.spec --define "_sourcedir `pwd`/dist"

srpm: sdist
	rpmbuild -bs imagefactory-plugins.spec --define "_sourcedir `pwd`/dist"

pylint:
	pylint --rcfile=pylint.conf imagefactory imgfac

unittests:
	python -m unittest discover -v

clean:
	rm -rf MANIFEST build dist imagefactory-plugins.spec
