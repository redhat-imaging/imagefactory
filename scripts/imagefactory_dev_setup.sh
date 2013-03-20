# N.B. Tested on Fedora 17 only.  Path's may change depending on your distro.

# Be sure to check these values are correct for your system.
PYTHON_PATH="/usr/lib/python2.7" 
IMAGEFACTORY_PLUGINS=/etc/imagefactory/plugins.d/

WORKING_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
IMAGEFACTORY_SRC=$(dirname "$WORKING_DIR")

sudo rm -rf $IMAGEFACTORY_PLUGINS/*

# Create symlinks to src plugins
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/EC2Cloud/EC2Cloud.info" $IMAGEFACTORY_PLUGINS/EC2Cloud.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/FedoraOS/FedoraOS.info" $IMAGEFACTORY_PLUGINS/FedoraOS.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/MockRPMBasedOS/MockRPMBasedOS.info" $IMAGEFACTORY_PLUGINS/MockRPMBasedOS.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/OpenStackCloud/OpenStackCloud.info" $IMAGEFACTORY_PLUGINS/OpenStackCloud.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/MockSphere/MockSphere.info" $IMAGEFACTORY_PLUGINS/MockSphere.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/RHEVM/RHEVM.info" $IMAGEFACTORY_PLUGINS/RHEVM.info
sudo ln -s "$IMAGEFACTORY_SRC/imagefactory_plugins/vSphere/vSphere.info" $IMAGEFACTORY_PLUGINS/vSphere.info

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
