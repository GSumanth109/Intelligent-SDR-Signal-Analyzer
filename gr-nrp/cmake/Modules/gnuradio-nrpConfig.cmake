find_package(PkgConfig)

PKG_CHECK_MODULES(PC_GR_NRP gnuradio-nrp)

FIND_PATH(
    GR_NRP_INCLUDE_DIRS
    NAMES gnuradio/nrp/api.h
    HINTS $ENV{NRP_DIR}/include
        ${PC_NRP_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    GR_NRP_LIBRARIES
    NAMES gnuradio-nrp
    HINTS $ENV{NRP_DIR}/lib
        ${PC_NRP_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
          )

include("${CMAKE_CURRENT_LIST_DIR}/gnuradio-nrpTarget.cmake")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(GR_NRP DEFAULT_MSG GR_NRP_LIBRARIES GR_NRP_INCLUDE_DIRS)
MARK_AS_ADVANCED(GR_NRP_LIBRARIES GR_NRP_INCLUDE_DIRS)
