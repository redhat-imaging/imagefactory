version:
	VERSION= `git describe | tr - _`
	sed -e "s/@VERSION@/${VERSION}/g" < imagefactory-plugins.spec.in > imagefactory-plugins.spec

sdist:
	python setup.py sdist

signed-rpm: sdist version
	rpmbuild -ba imagefactory-plugins.spec --sign --define "_sourcedir `pwd`/dist"

rpm: sdist version
	rpmbuild -ba imagefactory-plugins.spec --define "_sourcedir `pwd`/dist"

srpm: sdist version
	rpmbuild -bs imagefactory-plugins.spec --define "_sourcedir `pwd`/dist"

pylint:
	pylint --rcfile=pylint.conf imagefactory imgfac

unittests:
	python -m unittest discover -v

clean:
	rm -rf MANIFEST build dist imagefactory-plugins.spec version.txt
