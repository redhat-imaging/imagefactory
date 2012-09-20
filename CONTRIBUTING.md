Release Branching
-----------------

* With the first release candidate of a release, we want to create a branch named __release/*release-name*__. 

* From this point on, any development meant for a later release should be done on master and any fixes meant for the pending release should be done on the branch and merged up to master. 

* Milestones such as release candidates, the release itself, and any bug fix releases, should be done on the respective release branch and carried forward to master.

Tagging
-------

We have used a few different tagging conventions over time.  Below are the rough details:

* The current public facing release lives under the *release/1.0* branch in github and uses the version/tagging progression of 1.0.x.  Bugfix changes to this release will continue to be applied to this branch (or backported to it).

* A brief period of additional development of the v1 REST interface without plugins took place in the master branch with a version convention of 1.1.*.  The most recent tag for this series of changes is 1.1.2.  We have since committed to, and begun work on, a large scale change to both the REST interface and to a scheme for making OS and provider support dynamic by means of plugins.  As a result, it is unlikely we will ever formally "release" any of the changes in 1.1.2 as a new version using the original REST interface.  If we do, we will likely merge the changes up through 1.1.2 back into the release/1.0 branch after they have been stabilized.

* A large amount of development on the plugin scheme and v2 REST interface (among other things) has now been merged into the master branch.  The resulting factory daemon is not compatible with earlier clients.  We will continue to tag this sequence of work using 1.1.x, starting with 1.1.3.

* 1.2.0 is being reserved for the stable initial "Algiers" release.

* Work beyond Algiers will likely be tagged as 1.3.x

Error Handling
--------------

The V1 Factory code provides only a simple binary success/failure indication via the REST API.  To obtain additional details, users must review the Factory log file.  We'd like to improve on this.

So, we've added a "status_detail" field to our image objects in an attempt to improve the quality of error reporting that we pass through the API.  The convention we are attempting to follow across all builders is roughly as follows:

* The "status_detail" should be set to a human readable single-line explanation of the sub-task that the builder is working on.  For example: "Removing unique identifiers from image - Adding cloud information".  When an exception is encountered causing a build failure the status_detail can then be used to provide a meaningful error message to end users.  For example: "Failure encountered while: <status_detail>"

* Over time, we anticipate being able to identify particularly common failure modes that can be reliably detected in our exception handlers.  As we do this, we will begin to explicitly detect these details and then re-raise the exception as our own ImageFactoryException.  The text of an ImageFactoryException should itself be a simple, single-line human-readable explanation of the error encountered that can be displayed directly to UI users.  

    For example: 

        EC2 connection failed due to bad user credentials.  Please check credentials and try again.  

    This line can then be merged with the existing "status_detail" to provide a larger context for the error, in addition to the specific detail from the re-raised exception.  

* Full exception details should __always__ be logged via the Python logging subsystem. 
