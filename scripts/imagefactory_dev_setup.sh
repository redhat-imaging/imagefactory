# N.B. Tested on Fedora 17 only.  Path's may change depending on your distro.

# Be sure to check these values are correct for your system.
PYTHON_PATH="/usr/lib/python2.7" 
IMAGEFACTORY_PLUGINS=/etc/imagefactory/plugins.d/

WORKING_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
IMAGEFACTORY_SRC=$(dirname "$WORKING_DIR")

sudo rm -rf $IMAGEFACTORY_PLUGINS/*

# Create symlinks to src plugins
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/EC2/EC2.info" $IMAGEFACTORY_PLUGINS/EC2.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/TinMan/TinMan.info" $IMAGEFACTORY_PLUGINS/TinMan.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/MockOS/MockOS.info" $IMAGEFACTORY_PLUGINS/MockOS.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/OpenStack/OpenStack.info" $IMAGEFACTORY_PLUGINS/OpenStack.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/MockCloud/MockCloud.info" $IMAGEFACTORY_PLUGINS/MockCloud.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/RHEVM/RHEVM.info" $IMAGEFACTORY_PLUGINS/RHEVM.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/vSphere/vSphere.info" $IMAGEFACTORY_PLUGINS/vSphere.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/Rackspace/Rackspace.info" $IMAGEFACTORY_PLUGINS/Rackspace.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/OVA/OVA.info" $IMAGEFACTORY_PLUGINS/OVA.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/IndirectionCloud/IndirectionCloud.info" $IMAGEFACTORY_PLUGINS/IndirectionCloud.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/Docker/Docker.info" $IMAGEFACTORY_PLUGINS/Docker.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/Nova/Nova.info" $IMAGEFACTORY_PLUGINS/Nova.info

# Add Imagefactory src dirs to imgfacdev.pth
sudo sh -c "echo \"$IMAGEFACTORY_SRC\" > $PYTHON_PATH/site-packages/imgfacdev.pth"
sudo sh -c "echo \"$IMAGEFACTORY_SRC/imagefactory_plugins\" >> $PYTHON_PATH/site-packages/imgfacdev.pth"

echo "******************************************************"
echo "**    Imagefactory Development Environment Setup    **"
echo "**                                                  **"
echo "**             To start the server run:             **"
echo "**                                                  **"
echo "**         'sudo imagefactoryd --foreground'        **"
echo "**         # from imagefactory src directory        **"
echo "**                                                  **"
echo "**   For more options see: 'imagefactoryd --help'   **"
echo "******************************************************"
